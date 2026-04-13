"""GuardForge — PII Detection Precision/Recall Validator.

Runs the backend scanner against a labeled dataset and computes per-entity
precision and recall metrics per language. Prints a markdown report and
writes detailed results to `tests/validation_report.md`.

Run directly (requires backend on 8004):

    python tests/validate_precision_recall.py

Dataset format: list of {lang, text, expected[{type, value}]} entries in
`tests/pii_validation_dataset.json`. Values are matched as substrings of
detected entity values (tolerant: a detected "M. Jean Dupont" matches an
expected "Jean Dupont").
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import httpx


API_URL = os.environ.get("GUARDFORGE_API_URL", "http://127.0.0.1:8004")
API_KEY = os.environ.get("GUARDFORGE_API_KEY", "change-me-to-a-random-32-char-string")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

DATASET_PATH = Path(__file__).resolve().parent / "pii_validation_dataset.json"
REPORT_PATH = Path(__file__).resolve().parent / "validation_report.md"


def _load_dataset() -> list[dict]:
    if not DATASET_PATH.exists():
        raise SystemExit(f"dataset not found: {DATASET_PATH}")
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _match_found(expected_value: str, detected_value: str) -> bool:
    """Tolerant match: expected must be a substring of detected OR vice versa."""
    e = expected_value.strip().lower()
    d = detected_value.strip().lower()
    return e in d or d in e


def _score_example(
    example: dict,
    detected: list[dict],
) -> tuple[dict[str, dict[str, int]], list[dict]]:
    """Compare expected vs detected for one example.

    Returns:
        stats: {entity_type: {tp, fp, fn}}
        unmatched_expected: list of expected items that weren't found
    """
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    expected = [e for e in example.get("expected", []) if not e.get("_note", "").startswith("false-positive-ish")]
    matched_detected_idx: set[int] = set()
    unmatched_expected: list[dict] = []

    # For each expected entity, try to find a matching detected one
    for exp in expected:
        exp_type = exp["type"]
        exp_val = exp.get("value", "")
        found = False
        for i, det in enumerate(detected):
            if i in matched_detected_idx:
                continue
            if det["type"] == exp_type and _match_found(exp_val, det.get("value", "")):
                stats[exp_type]["tp"] += 1
                matched_detected_idx.add(i)
                found = True
                break
        if not found:
            stats[exp_type]["fn"] += 1
            unmatched_expected.append(exp)

    # Remaining detected entities are false positives
    # (exclude custom entities that aren't in our dataset scope)
    known_types = {
        "email", "phone_international", "credit_card", "ssn_us", "ssn_fr",
        "iban", "ipv4", "date_of_birth", "siret_fr", "siren_fr", "rib_fr",
        "steuer_id_de", "dni_es", "nie_es", "codice_fiscale_it",
        "passport_generic", "person_name",
    }
    for i, det in enumerate(detected):
        if i in matched_detected_idx:
            continue
        dt = det["type"]
        if dt in known_types:
            stats[dt]["fp"] += 1

    return stats, unmatched_expected


def _safe_div(num: int, den: int) -> float:
    return num / den if den > 0 else 0.0


def main() -> None:
    dataset = _load_dataset()
    print(f"Loaded {len(dataset)} test examples from {DATASET_PATH.name}")

    # by_lang → by_type → counters
    by_lang: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0}))
    overall: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    missed_examples: list[tuple[dict, list[dict]]] = []

    with httpx.Client(base_url=API_URL, headers=HEADERS, timeout=10.0) as client:
        for ex in dataset:
            lang = ex.get("lang", "?")
            text = ex["text"]
            try:
                res = client.post("/api/scan", json={"text": text, "strategy": "redact", "dry_run": True})
                res.raise_for_status()
            except Exception as exc:
                print(f"  [warn] scan failed for example: {exc}")
                continue
            detected = res.json().get("entities", [])
            stats, missed = _score_example(ex, detected)
            if missed:
                missed_examples.append((ex, missed))
            for etype, counters in stats.items():
                by_lang[lang][etype]["tp"] += counters["tp"]
                by_lang[lang][etype]["fp"] += counters["fp"]
                by_lang[lang][etype]["fn"] += counters["fn"]
                overall[etype]["tp"] += counters["tp"]
                overall[etype]["fp"] += counters["fp"]
                overall[etype]["fn"] += counters["fn"]

    # Format report
    lines: list[str] = [
        "# GuardForge PII Detection Validation Report",
        "",
        f"**Dataset**: {DATASET_PATH.name} ({len(dataset)} examples)",
        f"**Target**: {API_URL}",
        "",
        "## Methodology",
        "",
        "- Each example is a text with a ground-truth list of expected PII entities.",
        "- Detection is performed via `POST /api/scan?dry_run=true` (no anonymization).",
        "- **TP** (true positive): expected entity found with matching type and value (substring tolerance).",
        "- **FP** (false positive): detected entity of a known type that has no matching expected entity.",
        "- **FN** (false negative): expected entity not found in detection results.",
        "- **Precision** = TP / (TP + FP) — accuracy of positives.",
        "- **Recall** = TP / (TP + FN) — coverage of ground truth.",
        "- **F1** = 2·P·R / (P + R) — harmonic mean.",
        "",
        "## Overall metrics (all languages)",
        "",
        "| Entity type | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    def _format_row(etype: str, c: dict) -> str:
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        p = _safe_div(tp, tp + fp)
        r = _safe_div(tp, tp + fn)
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return f"| {etype} | {tp} | {fp} | {fn} | {p:.2f} | {r:.2f} | {f1:.2f} |"

    for etype in sorted(overall.keys()):
        lines.append(_format_row(etype, overall[etype]))

    # Aggregate totals
    tot_tp = sum(c["tp"] for c in overall.values())
    tot_fp = sum(c["fp"] for c in overall.values())
    tot_fn = sum(c["fn"] for c in overall.values())
    tot_p = _safe_div(tot_tp, tot_tp + tot_fp)
    tot_r = _safe_div(tot_tp, tot_tp + tot_fn)
    tot_f1 = 2 * tot_p * tot_r / (tot_p + tot_r) if (tot_p + tot_r) > 0 else 0.0
    lines.append(f"| **ALL** | **{tot_tp}** | **{tot_fp}** | **{tot_fn}** | **{tot_p:.2f}** | **{tot_r:.2f}** | **{tot_f1:.2f}** |")
    lines.append("")

    # Per-language breakdown
    lines.append("## Per-language breakdown")
    for lang in sorted(by_lang.keys()):
        lines.append(f"\n### Language: `{lang}`")
        lines.append("")
        lines.append("| Entity type | TP | FP | FN | Precision | Recall | F1 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for etype in sorted(by_lang[lang].keys()):
            lines.append(_format_row(etype, by_lang[lang][etype]))

    # Missed examples
    if missed_examples:
        lines.append("\n## Missed detections (sample)")
        for ex, missed in missed_examples[:10]:
            short = ex["text"][:80] + ("..." if len(ex["text"]) > 80 else "")
            lines.append(f"\n- `{ex['lang']}` — {short!r}")
            for m in missed:
                lines.append(f"  - missing **{m['type']}** = `{m.get('value','')}`")
        if len(missed_examples) > 10:
            lines.append(f"\n_(and {len(missed_examples) - 10} more)_")

    report = "\n".join(lines)
    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
