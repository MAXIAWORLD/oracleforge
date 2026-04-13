"""One-shot: add the 10 new jurisdiction policy descriptions to all 15 message files.

Additive — leaves existing 6 descriptions (strict/moderate/permissive/gdpr/hipaa/pci_dss) intact.
Adds: eu_ai_act, ccpa, lgpd, pipeda, appi, pdpa_sg, popia, dpdp_in, pipl_cn, privacy_au

Idempotent: re-running just overwrites the new keys.
"""

from __future__ import annotations

import json
from pathlib import Path

NEW_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "en": {
        "eu_ai_act": "EU AI Act compliance — minimize PII in high-risk AI systems",
        "ccpa": "CCPA / CPRA compliance — anonymize California consumer data",
        "lgpd": "LGPD compliance — anonymize Brazilian personal data",
        "pipeda": "PIPEDA compliance — anonymize Canadian personal data",
        "appi": "APPI compliance — anonymize Japanese personal data",
        "pdpa_sg": "PDPA Singapore compliance — anonymize personal data",
        "popia": "POPIA compliance — anonymize South African personal data",
        "dpdp_in": "DPDP Act compliance — anonymize Indian personal data",
        "pipl_cn": "PIPL compliance — block cross-border PII transfers",
        "privacy_au": "Privacy Act 1988 compliance — anonymize Australian personal data",
    },
    "fr": {
        "eu_ai_act": "Conformite EU AI Act — minimiser les PII dans les systemes IA a haut risque",
        "ccpa": "Conformite CCPA / CPRA — anonymiser les donnees des consommateurs californiens",
        "lgpd": "Conformite LGPD — anonymiser les donnees personnelles bresiliennes",
        "pipeda": "Conformite PIPEDA — anonymiser les donnees personnelles canadiennes",
        "appi": "Conformite APPI — anonymiser les donnees personnelles japonaises",
        "pdpa_sg": "Conformite PDPA Singapour — anonymiser les donnees personnelles",
        "popia": "Conformite POPIA — anonymiser les donnees personnelles sud-africaines",
        "dpdp_in": "Conformite DPDP Act — anonymiser les donnees personnelles indiennes",
        "pipl_cn": "Conformite PIPL — bloquer les transferts transfrontaliers de PII",
        "privacy_au": "Conformite Privacy Act 1988 — anonymiser les donnees personnelles australiennes",
    },
    "es": {
        "eu_ai_act": "Cumplimiento EU AI Act — minimizar PII en sistemas de IA de alto riesgo",
        "ccpa": "Cumplimiento CCPA / CPRA — anonimizar datos de consumidores de California",
        "lgpd": "Cumplimiento LGPD — anonimizar datos personales brasileños",
        "pipeda": "Cumplimiento PIPEDA — anonimizar datos personales canadienses",
        "appi": "Cumplimiento APPI — anonimizar datos personales japoneses",
        "pdpa_sg": "Cumplimiento PDPA Singapur — anonimizar datos personales",
        "popia": "Cumplimiento POPIA — anonimizar datos personales sudafricanos",
        "dpdp_in": "Cumplimiento DPDP Act — anonimizar datos personales indios",
        "pipl_cn": "Cumplimiento PIPL — bloquear transferencias transfronterizas de PII",
        "privacy_au": "Cumplimiento Privacy Act 1988 — anonimizar datos personales australianos",
    },
    "de": {
        "eu_ai_act": "EU AI Act-Konformität — PII in Hochrisiko-KI-Systemen minimieren",
        "ccpa": "CCPA / CPRA-Konformität — kalifornische Verbraucherdaten anonymisieren",
        "lgpd": "LGPD-Konformität — brasilianische personenbezogene Daten anonymisieren",
        "pipeda": "PIPEDA-Konformität — kanadische personenbezogene Daten anonymisieren",
        "appi": "APPI-Konformität — japanische personenbezogene Daten anonymisieren",
        "pdpa_sg": "PDPA Singapur-Konformität — personenbezogene Daten anonymisieren",
        "popia": "POPIA-Konformität — südafrikanische personenbezogene Daten anonymisieren",
        "dpdp_in": "DPDP Act-Konformität — indische personenbezogene Daten anonymisieren",
        "pipl_cn": "PIPL-Konformität — grenzüberschreitende PII-Transfers blockieren",
        "privacy_au": "Privacy Act 1988-Konformität — australische personenbezogene Daten anonymisieren",
    },
    "it": {
        "eu_ai_act": "Conformità EU AI Act — ridurre i PII nei sistemi IA ad alto rischio",
        "ccpa": "Conformità CCPA / CPRA — anonimizzare i dati dei consumatori californiani",
        "lgpd": "Conformità LGPD — anonimizzare i dati personali brasiliani",
        "pipeda": "Conformità PIPEDA — anonimizzare i dati personali canadesi",
        "appi": "Conformità APPI — anonimizzare i dati personali giapponesi",
        "pdpa_sg": "Conformità PDPA Singapore — anonimizzare i dati personali",
        "popia": "Conformità POPIA — anonimizzare i dati personali sudafricani",
        "dpdp_in": "Conformità DPDP Act — anonimizzare i dati personali indiani",
        "pipl_cn": "Conformità PIPL — bloccare i trasferimenti transfrontalieri di PII",
        "privacy_au": "Conformità Privacy Act 1988 — anonimizzare i dati personali australiani",
    },
    "pt": {
        "eu_ai_act": "Conformidade EU AI Act — minimizar PII em sistemas de IA de alto risco",
        "ccpa": "Conformidade CCPA / CPRA — anonimizar dados de consumidores da Califórnia",
        "lgpd": "Conformidade LGPD — anonimizar dados pessoais brasileiros",
        "pipeda": "Conformidade PIPEDA — anonimizar dados pessoais canadenses",
        "appi": "Conformidade APPI — anonimizar dados pessoais japoneses",
        "pdpa_sg": "Conformidade PDPA Singapura — anonimizar dados pessoais",
        "popia": "Conformidade POPIA — anonimizar dados pessoais sul-africanos",
        "dpdp_in": "Conformidade DPDP Act — anonimizar dados pessoais indianos",
        "pipl_cn": "Conformidade PIPL — bloquear transferências transfronteiriças de PII",
        "privacy_au": "Conformidade Privacy Act 1988 — anonimizar dados pessoais australianos",
    },
    "nl": {
        "eu_ai_act": "EU AI Act-naleving — minimaliseer PII in AI-systemen met hoog risico",
        "ccpa": "CCPA / CPRA-naleving — anonimiseer Californische consumentengegevens",
        "lgpd": "LGPD-naleving — anonimiseer Braziliaanse persoonsgegevens",
        "pipeda": "PIPEDA-naleving — anonimiseer Canadese persoonsgegevens",
        "appi": "APPI-naleving — anonimiseer Japanse persoonsgegevens",
        "pdpa_sg": "PDPA Singapore-naleving — anonimiseer persoonsgegevens",
        "popia": "POPIA-naleving — anonimiseer Zuid-Afrikaanse persoonsgegevens",
        "dpdp_in": "DPDP Act-naleving — anonimiseer Indiase persoonsgegevens",
        "pipl_cn": "PIPL-naleving — blokkeer grensoverschrijdende PII-overdrachten",
        "privacy_au": "Privacy Act 1988-naleving — anonimiseer Australische persoonsgegevens",
    },
    "pl": {
        "eu_ai_act": "Zgodność z EU AI Act — minimalizuj PII w systemach AI wysokiego ryzyka",
        "ccpa": "Zgodność z CCPA / CPRA — anonimizuj dane konsumentów z Kalifornii",
        "lgpd": "Zgodność z LGPD — anonimizuj brazylijskie dane osobowe",
        "pipeda": "Zgodność z PIPEDA — anonimizuj kanadyjskie dane osobowe",
        "appi": "Zgodność z APPI — anonimizuj japońskie dane osobowe",
        "pdpa_sg": "Zgodność z PDPA Singapur — anonimizuj dane osobowe",
        "popia": "Zgodność z POPIA — anonimizuj dane osobowe z RPA",
        "dpdp_in": "Zgodność z DPDP Act — anonimizuj indyjskie dane osobowe",
        "pipl_cn": "Zgodność z PIPL — blokuj transgraniczny transfer PII",
        "privacy_au": "Zgodność z Privacy Act 1988 — anonimizuj australijskie dane osobowe",
    },
    "ru": {
        "eu_ai_act": "Соответствие EU AI Act — минимизация PII в ИИ-системах высокого риска",
        "ccpa": "Соответствие CCPA / CPRA — анонимизация данных потребителей Калифорнии",
        "lgpd": "Соответствие LGPD — анонимизация бразильских персональных данных",
        "pipeda": "Соответствие PIPEDA — анонимизация канадских персональных данных",
        "appi": "Соответствие APPI — анонимизация японских персональных данных",
        "pdpa_sg": "Соответствие PDPA Сингапура — анонимизация персональных данных",
        "popia": "Соответствие POPIA — анонимизация южноафриканских персональных данных",
        "dpdp_in": "Соответствие DPDP Act — анонимизация индийских персональных данных",
        "pipl_cn": "Соответствие PIPL — блокировка трансграничных передач PII",
        "privacy_au": "Соответствие Privacy Act 1988 — анонимизация австралийских персональных данных",
    },
    "tr": {
        "eu_ai_act": "EU AI Act uyumluluğu — yüksek riskli AI sistemlerinde PII'yi minimize et",
        "ccpa": "CCPA / CPRA uyumluluğu — Kaliforniya tüketici verilerini anonimleştir",
        "lgpd": "LGPD uyumluluğu — Brezilya kişisel verilerini anonimleştir",
        "pipeda": "PIPEDA uyumluluğu — Kanada kişisel verilerini anonimleştir",
        "appi": "APPI uyumluluğu — Japonya kişisel verilerini anonimleştir",
        "pdpa_sg": "PDPA Singapur uyumluluğu — kişisel verileri anonimleştir",
        "popia": "POPIA uyumluluğu — Güney Afrika kişisel verilerini anonimleştir",
        "dpdp_in": "DPDP Act uyumluluğu — Hindistan kişisel verilerini anonimleştir",
        "pipl_cn": "PIPL uyumluluğu — sınır ötesi PII transferlerini engelle",
        "privacy_au": "Privacy Act 1988 uyumluluğu — Avustralya kişisel verilerini anonimleştir",
    },
    "ar": {
        "eu_ai_act": "الامتثال لقانون EU AI Act — تقليل بيانات PII في أنظمة الذكاء الاصطناعي عالية المخاطر",
        "ccpa": "الامتثال لـ CCPA / CPRA — إخفاء هوية بيانات مستهلكي كاليفورنيا",
        "lgpd": "الامتثال لـ LGPD — إخفاء هوية البيانات الشخصية البرازيلية",
        "pipeda": "الامتثال لـ PIPEDA — إخفاء هوية البيانات الشخصية الكندية",
        "appi": "الامتثال لـ APPI — إخفاء هوية البيانات الشخصية اليابانية",
        "pdpa_sg": "الامتثال لـ PDPA سنغافورة — إخفاء هوية البيانات الشخصية",
        "popia": "الامتثال لـ POPIA — إخفاء هوية البيانات الشخصية لجنوب أفريقيا",
        "dpdp_in": "الامتثال لـ DPDP Act — إخفاء هوية البيانات الشخصية الهندية",
        "pipl_cn": "الامتثال لـ PIPL — حظر عمليات نقل PII عبر الحدود",
        "privacy_au": "الامتثال لقانون Privacy Act 1988 — إخفاء هوية البيانات الشخصية الأسترالية",
    },
    "hi": {
        "eu_ai_act": "EU AI Act अनुपालन — उच्च जोखिम वाली AI प्रणालियों में PII को कम करें",
        "ccpa": "CCPA / CPRA अनुपालन — कैलिफोर्निया उपभोक्ता डेटा को गुमनाम करें",
        "lgpd": "LGPD अनुपालन — ब्राजीलियाई व्यक्तिगत डेटा को गुमनाम करें",
        "pipeda": "PIPEDA अनुपालन — कनाडाई व्यक्तिगत डेटा को गुमनाम करें",
        "appi": "APPI अनुपालन — जापानी व्यक्तिगत डेटा को गुमनाम करें",
        "pdpa_sg": "PDPA सिंगापुर अनुपालन — व्यक्तिगत डेटा को गुमनाम करें",
        "popia": "POPIA अनुपालन — दक्षिण अफ्रीकी व्यक्तिगत डेटा को गुमनाम करें",
        "dpdp_in": "DPDP Act अनुपालन — भारतीय व्यक्तिगत डेटा को गुमनाम करें",
        "pipl_cn": "PIPL अनुपालन — सीमा-पार PII स्थानांतरण को ब्लॉक करें",
        "privacy_au": "Privacy Act 1988 अनुपालन — ऑस्ट्रेलियाई व्यक्तिगत डेटा को गुमनाम करें",
    },
    "ja": {
        "eu_ai_act": "EU AI Act準拠 — 高リスクAIシステムでPIIを最小化",
        "ccpa": "CCPA / CPRA準拠 — カリフォルニア消費者データを匿名化",
        "lgpd": "LGPD準拠 — ブラジルの個人データを匿名化",
        "pipeda": "PIPEDA準拠 — カナダの個人データを匿名化",
        "appi": "APPI準拠 — 日本の個人データを匿名化",
        "pdpa_sg": "PDPAシンガポール準拠 — 個人データを匿名化",
        "popia": "POPIA準拠 — 南アフリカの個人データを匿名化",
        "dpdp_in": "DPDP Act準拠 — インドの個人データを匿名化",
        "pipl_cn": "PIPL準拠 — 国境を越えるPII転送をブロック",
        "privacy_au": "Privacy Act 1988準拠 — オーストラリアの個人データを匿名化",
    },
    "ko": {
        "eu_ai_act": "EU AI Act 준수 — 고위험 AI 시스템에서 PII 최소화",
        "ccpa": "CCPA / CPRA 준수 — 캘리포니아 소비자 데이터 익명화",
        "lgpd": "LGPD 준수 — 브라질 개인 데이터 익명화",
        "pipeda": "PIPEDA 준수 — 캐나다 개인 데이터 익명화",
        "appi": "APPI 준수 — 일본 개인 데이터 익명화",
        "pdpa_sg": "PDPA 싱가포르 준수 — 개인 데이터 익명화",
        "popia": "POPIA 준수 — 남아프리카 개인 데이터 익명화",
        "dpdp_in": "DPDP Act 준수 — 인도 개인 데이터 익명화",
        "pipl_cn": "PIPL 준수 — 국경 간 PII 전송 차단",
        "privacy_au": "Privacy Act 1988 준수 — 호주 개인 데이터 익명화",
    },
    "zh": {
        "eu_ai_act": "EU AI Act 合规 — 在高风险 AI 系统中最小化 PII",
        "ccpa": "CCPA / CPRA 合规 — 匿名化加州消费者数据",
        "lgpd": "LGPD 合规 — 匿名化巴西个人数据",
        "pipeda": "PIPEDA 合规 — 匿名化加拿大个人数据",
        "appi": "APPI 合规 — 匿名化日本个人数据",
        "pdpa_sg": "PDPA 新加坡合规 — 匿名化个人数据",
        "popia": "POPIA 合规 — 匿名化南非个人数据",
        "dpdp_in": "DPDP Act 合规 — 匿名化印度个人数据",
        "pipl_cn": "PIPL 合规 — 阻止跨境 PII 传输",
        "privacy_au": "Privacy Act 1988 合规 — 匿名化澳大利亚个人数据",
    },
}

MESSAGES_DIR = Path(__file__).resolve().parent.parent / "src" / "messages"


def main() -> None:
    if not MESSAGES_DIR.is_dir():
        raise SystemExit(f"messages dir not found: {MESSAGES_DIR}")

    updated: list[str] = []
    for lang, new_descs in NEW_DESCRIPTIONS.items():
        path = MESSAGES_DIR / f"{lang}.json"
        if not path.exists():
            print(f"SKIP missing: {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        policies = data.setdefault("policies", {})
        descriptions = policies.setdefault("descriptions", {})
        # Merge: new keys added, existing keys preserved unless conflict
        descriptions.update(new_descs)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        updated.append(lang)

    print(f"updated {len(updated)} files: {', '.join(updated)}")
    print(f"added {len(NEW_DESCRIPTIONS['en'])} new keys per file")


if __name__ == "__main__":
    main()
