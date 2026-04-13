"""One-shot script: add policy.descriptions sub-block to all 15 message files.

Run once after switching policy descriptions from backend to frontend i18n.
Idempotent: re-running just overwrites the descriptions block.
"""

from __future__ import annotations

import json
from pathlib import Path

DESCRIPTIONS: dict[str, dict[str, str]] = {
    "en": {
        "strict": "Block all PII — maximum safety",
        "moderate": "Anonymize PII before processing",
        "permissive": "Warn on PII but allow processing",
        "gdpr": "GDPR compliance — anonymize personal data",
        "hipaa": "HIPAA compliance — block all health-related PII",
        "pci_dss": "PCI-DSS compliance — block payment data",
    },
    "fr": {
        "strict": "Bloquer toutes les PII — securite maximale",
        "moderate": "Anonymiser les PII avant traitement",
        "permissive": "Avertir sur les PII mais autoriser le traitement",
        "gdpr": "Conformite RGPD — anonymiser les donnees personnelles",
        "hipaa": "Conformite HIPAA — bloquer toutes les PII de sante",
        "pci_dss": "Conformite PCI-DSS — bloquer les donnees de paiement",
    },
    "es": {
        "strict": "Bloquear todos los PII — máxima seguridad",
        "moderate": "Anonimizar los PII antes del procesamiento",
        "permissive": "Advertir sobre PII pero permitir el procesamiento",
        "gdpr": "Cumplimiento RGPD — anonimizar datos personales",
        "hipaa": "Cumplimiento HIPAA — bloquear todos los PII relacionados con la salud",
        "pci_dss": "Cumplimiento PCI-DSS — bloquear datos de pago",
    },
    "de": {
        "strict": "Alle PII blockieren — maximale Sicherheit",
        "moderate": "PII vor der Verarbeitung anonymisieren",
        "permissive": "Bei PII warnen, aber Verarbeitung erlauben",
        "gdpr": "DSGVO-Konformität — personenbezogene Daten anonymisieren",
        "hipaa": "HIPAA-Konformität — alle gesundheitsbezogenen PII blockieren",
        "pci_dss": "PCI-DSS-Konformität — Zahlungsdaten blockieren",
    },
    "it": {
        "strict": "Blocca tutti i PII — massima sicurezza",
        "moderate": "Anonimizza i PII prima dell'elaborazione",
        "permissive": "Avvisa sui PII ma consenti l'elaborazione",
        "gdpr": "Conformità GDPR — anonimizza i dati personali",
        "hipaa": "Conformità HIPAA — blocca tutti i PII sanitari",
        "pci_dss": "Conformità PCI-DSS — blocca i dati di pagamento",
    },
    "pt": {
        "strict": "Bloquear todos os PII — segurança máxima",
        "moderate": "Anonimizar PII antes do processamento",
        "permissive": "Avisar sobre PII mas permitir o processamento",
        "gdpr": "Conformidade RGPD — anonimizar dados pessoais",
        "hipaa": "Conformidade HIPAA — bloquear todos os PII de saúde",
        "pci_dss": "Conformidade PCI-DSS — bloquear dados de pagamento",
    },
    "nl": {
        "strict": "Blokkeer alle PII — maximale veiligheid",
        "moderate": "Anonimiseer PII voor verwerking",
        "permissive": "Waarschuw bij PII maar sta verwerking toe",
        "gdpr": "AVG-naleving — anonimiseer persoonsgegevens",
        "hipaa": "HIPAA-naleving — blokkeer alle gezondheidsgerelateerde PII",
        "pci_dss": "PCI-DSS-naleving — blokkeer betalingsgegevens",
    },
    "pl": {
        "strict": "Blokuj wszystkie dane PII — maksymalne bezpieczeństwo",
        "moderate": "Anonimizuj dane PII przed przetwarzaniem",
        "permissive": "Ostrzegaj o PII, ale zezwalaj na przetwarzanie",
        "gdpr": "Zgodność z RODO — anonimizuj dane osobowe",
        "hipaa": "Zgodność z HIPAA — blokuj wszystkie PII związane ze zdrowiem",
        "pci_dss": "Zgodność z PCI-DSS — blokuj dane płatnicze",
    },
    "ru": {
        "strict": "Блокировать все PII — максимальная безопасность",
        "moderate": "Анонимизировать PII перед обработкой",
        "permissive": "Предупреждать о PII, но разрешать обработку",
        "gdpr": "Соответствие GDPR — анонимизация персональных данных",
        "hipaa": "Соответствие HIPAA — блокировать все медицинские PII",
        "pci_dss": "Соответствие PCI-DSS — блокировать платёжные данные",
    },
    "tr": {
        "strict": "Tüm PII'leri engelle — maksimum güvenlik",
        "moderate": "PII'leri işlemden önce anonimleştir",
        "permissive": "PII konusunda uyar ancak işlemeye izin ver",
        "gdpr": "GDPR uyumluluğu — kişisel verileri anonimleştir",
        "hipaa": "HIPAA uyumluluğu — tüm sağlık PII'lerini engelle",
        "pci_dss": "PCI-DSS uyumluluğu — ödeme verilerini engelle",
    },
    "ar": {
        "strict": "حظر جميع بيانات PII — أقصى حماية",
        "moderate": "إخفاء هوية بيانات PII قبل المعالجة",
        "permissive": "التحذير من بيانات PII مع السماح بالمعالجة",
        "gdpr": "الامتثال للائحة GDPR — إخفاء هوية البيانات الشخصية",
        "hipaa": "الامتثال لـ HIPAA — حظر جميع بيانات PII الصحية",
        "pci_dss": "الامتثال لـ PCI-DSS — حظر بيانات الدفع",
    },
    "hi": {
        "strict": "सभी PII को ब्लॉक करें — अधिकतम सुरक्षा",
        "moderate": "प्रोसेसिंग से पहले PII को गुमनाम करें",
        "permissive": "PII पर चेतावनी दें लेकिन प्रोसेसिंग की अनुमति दें",
        "gdpr": "GDPR अनुपालन — व्यक्तिगत डेटा को गुमनाम करें",
        "hipaa": "HIPAA अनुपालन — सभी स्वास्थ्य संबंधी PII को ब्लॉक करें",
        "pci_dss": "PCI-DSS अनुपालन — भुगतान डेटा को ब्लॉक करें",
    },
    "ja": {
        "strict": "すべてのPIIをブロック — 最大限の安全性",
        "moderate": "処理前にPIIを匿名化",
        "permissive": "PIIを警告するが処理を許可",
        "gdpr": "GDPR準拠 — 個人データを匿名化",
        "hipaa": "HIPAA準拠 — すべての健康関連PIIをブロック",
        "pci_dss": "PCI-DSS準拠 — 支払いデータをブロック",
    },
    "ko": {
        "strict": "모든 PII 차단 — 최대 보안",
        "moderate": "처리 전 PII 익명화",
        "permissive": "PII 경고하지만 처리 허용",
        "gdpr": "GDPR 준수 — 개인 데이터 익명화",
        "hipaa": "HIPAA 준수 — 모든 건강 관련 PII 차단",
        "pci_dss": "PCI-DSS 준수 — 결제 데이터 차단",
    },
    "zh": {
        "strict": "阻止所有 PII — 最高安全级别",
        "moderate": "处理前将 PII 匿名化",
        "permissive": "对 PII 发出警告但允许处理",
        "gdpr": "GDPR 合规 — 匿名化个人数据",
        "hipaa": "HIPAA 合规 — 阻止所有健康相关 PII",
        "pci_dss": "PCI-DSS 合规 — 阻止支付数据",
    },
}

MESSAGES_DIR = Path(__file__).resolve().parent.parent / "src" / "messages"

def main() -> None:
    if not MESSAGES_DIR.is_dir():
        raise SystemExit(f"messages dir not found: {MESSAGES_DIR}")

    updated: list[str] = []
    for lang, descs in DESCRIPTIONS.items():
        path = MESSAGES_DIR / f"{lang}.json"
        if not path.exists():
            print(f"SKIP missing: {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            print(f"SKIP non-dict: {path}")
            continue
        policies = data.setdefault("policies", {})
        if not isinstance(policies, dict):
            print(f"SKIP policies non-dict: {path}")
            continue
        policies["descriptions"] = descs
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        updated.append(lang)

    print(f"updated {len(updated)} files: {', '.join(updated)}")


if __name__ == "__main__":
    main()
