"""GuardForge — Performance benchmark script.

Measures p50/p95/p99 latency on the /api/scan and /api/tokenize endpoints
over a realistic mix of input payloads. Not a pytest — run directly:

    python tests/benchmark_performance.py

Output is a human-readable report and a JSON file at
`tests/benchmark_results.json` that can be diffed across releases.

Requires a running backend at http://localhost:8004.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path
from typing import Callable

import httpx


API_URL = os.environ.get("GUARDFORGE_API_URL", "http://127.0.0.1:8004")
API_KEY = os.environ.get("GUARDFORGE_API_KEY", "change-me-to-a-random-32-char-string")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


# ── Test payloads (realistic distribution) ───────────────────────

SHORT_TEXT_NO_PII = "The weather is nice today and everything is fine."

SHORT_TEXT_ONE_PII = "Contact me at alice@example.com please."

MEDIUM_TEXT_FEW_PII = (
    "Customer Mr Jean Dupont requested a refund for order #12345. "
    "His email is jean.dupont@example.fr and phone is +33 6 12 34 56 78. "
    "The order was shipped on 15/03/2024 and delivered successfully."
)

LONG_TEXT_MANY_PII = (
    "Dear Mrs Maria Garcia,\n\n"
    "We confirm your order. Invoice details follow:\n"
    "- IBAN: FR7630006000011234567890189\n"
    "- Card: 4532015112830366\n"
    "- SIRET: 73282932000074\n"
    "- DNI: 12345678Z\n"
    "- Email: maria.garcia@empresa.es\n"
    "- Phone: +34 612 345 678\n"
    "- Date of birth: 15/03/1985\n"
    "- Internal ref: TICKET-789012\n"
    "Your customer support representative is M. Pierre Martin "
    "(pierre.martin@support.fr).\n\n"
    "Best regards,\nThe team"
)

VERY_LONG_TEXT = MEDIUM_TEXT_FEW_PII * 20  # ~3000 chars

# Distribution of payloads (rotating through these during the benchmark)
PAYLOAD_MIX: list[tuple[str, str]] = [
    ("short_no_pii", SHORT_TEXT_NO_PII),
    ("short_1_pii", SHORT_TEXT_ONE_PII),
    ("medium_few_pii", MEDIUM_TEXT_FEW_PII),
    ("long_many_pii", LONG_TEXT_MANY_PII),
    ("medium_few_pii", MEDIUM_TEXT_FEW_PII),  # weighted more
    ("short_1_pii", SHORT_TEXT_ONE_PII),  # weighted more
    ("very_long", VERY_LONG_TEXT),
]


def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile of a sorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def _benchmark_endpoint(
    client: httpx.Client,
    label: str,
    total_requests: int,
    fn: Callable[[httpx.Client, tuple[str, str]], float],
) -> dict:
    """Run `fn` over total_requests payloads and return aggregate stats."""
    latencies_ms: list[float] = []
    errors = 0
    by_type: dict[str, list[float]] = {}
    start_ts = time.perf_counter()

    for i in range(total_requests):
        payload_type, payload_text = PAYLOAD_MIX[i % len(PAYLOAD_MIX)]
        try:
            elapsed_ms = fn(client, (payload_type, payload_text))
            latencies_ms.append(elapsed_ms)
            by_type.setdefault(payload_type, []).append(elapsed_ms)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            if errors < 3:
                print(f"  [{label}] request {i} failed: {type(exc).__name__}: {exc}")

    total_time = time.perf_counter() - start_ts
    return {
        "endpoint": label,
        "total_requests": total_requests,
        "errors": errors,
        "successes": len(latencies_ms),
        "total_duration_s": round(total_time, 2),
        "rps": round(len(latencies_ms) / total_time, 1) if total_time > 0 else 0,
        "latency_ms": {
            "min": round(min(latencies_ms), 2) if latencies_ms else 0,
            "mean": round(statistics.mean(latencies_ms), 2) if latencies_ms else 0,
            "p50": round(_percentile(latencies_ms, 0.50), 2),
            "p95": round(_percentile(latencies_ms, 0.95), 2),
            "p99": round(_percentile(latencies_ms, 0.99), 2),
            "max": round(max(latencies_ms), 2) if latencies_ms else 0,
        },
        "latency_by_payload_ms": {
            ptype: {
                "count": len(vs),
                "p50": round(_percentile(vs, 0.50), 2),
                "p95": round(_percentile(vs, 0.95), 2),
            }
            for ptype, vs in by_type.items()
        },
    }


def _scan_call(client: httpx.Client, payload: tuple[str, str]) -> float:
    t0 = time.perf_counter()
    res = client.post("/api/scan", json={"text": payload[1], "strategy": "redact"})
    res.raise_for_status()
    return (time.perf_counter() - t0) * 1000


def _tokenize_call(client: httpx.Client, payload: tuple[str, str]) -> float:
    t0 = time.perf_counter()
    res = client.post("/api/tokenize", json={"text": payload[1]})
    res.raise_for_status()
    return (time.perf_counter() - t0) * 1000


def _format_report(results: list[dict]) -> str:
    """Format results as a human-readable markdown report."""
    lines = ["# GuardForge Performance Benchmark Report\n"]
    lines.append(f"**Target**: `{API_URL}`\n")
    for r in results:
        lat = r["latency_ms"]
        lines.append(f"## `{r['endpoint']}`\n")
        lines.append(f"- Requests: {r['successes']}/{r['total_requests']} ({r['errors']} errors)")
        lines.append(f"- Total duration: {r['total_duration_s']}s")
        lines.append(f"- Throughput: {r['rps']} req/s")
        lines.append(f"- Latency p50: **{lat['p50']} ms**")
        lines.append(f"- Latency p95: **{lat['p95']} ms**")
        lines.append(f"- Latency p99: {lat['p99']} ms")
        lines.append(f"- Latency min/mean/max: {lat['min']} / {lat['mean']} / {lat['max']} ms")
        lines.append("\n### By payload type")
        for ptype, stats in r["latency_by_payload_ms"].items():
            lines.append(f"- `{ptype}` ({stats['count']} req): p50={stats['p50']}ms p95={stats['p95']}ms")
        lines.append("")
    return "\n".join(lines)


def main(total_requests: int = 1000) -> None:
    print(f"GuardForge Performance Benchmark — {total_requests} requests per endpoint")
    print(f"Target: {API_URL}")
    print(f"Starting {time.strftime('%H:%M:%S')}...\n")

    with httpx.Client(base_url=API_URL, headers=HEADERS, timeout=30.0) as client:
        # Quick health check
        h = client.get("/health")
        if h.status_code != 200:
            raise SystemExit(f"Backend health check failed: {h.status_code}")
        print(f"Backend healthy: {h.json()}\n")

        # Benchmark /api/scan
        print(f"Benchmarking /api/scan ...")
        scan_result = _benchmark_endpoint(client, "/api/scan", total_requests, _scan_call)
        print(f"  done in {scan_result['total_duration_s']}s (p50={scan_result['latency_ms']['p50']}ms, p95={scan_result['latency_ms']['p95']}ms)\n")

        # Benchmark /api/tokenize
        print(f"Benchmarking /api/tokenize ...")
        tok_result = _benchmark_endpoint(client, "/api/tokenize", total_requests, _tokenize_call)
        print(f"  done in {tok_result['total_duration_s']}s (p50={tok_result['latency_ms']['p50']}ms, p95={tok_result['latency_ms']['p95']}ms)\n")

    results = [scan_result, tok_result]

    report = _format_report(results)
    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)

    out_dir = Path(__file__).resolve().parent
    json_path = out_dir / "benchmark_results.json"
    md_path = out_dir / "benchmark_results.md"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    md_path.write_text(report, encoding="utf-8")
    print(f"\nResults written to:\n  {json_path}\n  {md_path}")


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    main(n)
