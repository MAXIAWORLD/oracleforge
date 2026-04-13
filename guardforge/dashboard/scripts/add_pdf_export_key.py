"""Add reports.export_pdf_btn key to all 15 message files."""

from __future__ import annotations

import json
from pathlib import Path

LABELS: dict[str, str] = {
    "en": "Export PDF",
    "fr": "Exporter PDF",
    "es": "Exportar PDF",
    "de": "PDF exportieren",
    "it": "Esporta PDF",
    "pt": "Exportar PDF",
    "nl": "PDF exporteren",
    "pl": "Eksportuj PDF",
    "ru": "Экспорт PDF",
    "tr": "PDF dışa aktar",
    "ar": "تصدير PDF",
    "hi": "PDF निर्यात करें",
    "ja": "PDFをエクスポート",
    "ko": "PDF 내보내기",
    "zh": "导出 PDF",
}

MESSAGES_DIR = Path(__file__).resolve().parent.parent / "src" / "messages"


def main() -> None:
    if not MESSAGES_DIR.is_dir():
        raise SystemExit(f"messages dir not found: {MESSAGES_DIR}")

    updated: list[str] = []
    for lang, label in LABELS.items():
        path = MESSAGES_DIR / f"{lang}.json"
        if not path.exists():
            print(f"SKIP missing: {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        reports = data.setdefault("reports", {})
        reports["export_pdf_btn"] = label
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        updated.append(lang)

    print(f"updated {len(updated)} files: {', '.join(updated)}")


if __name__ == "__main__":
    main()
