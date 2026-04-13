# GuardForge PII Detection Validation Report

**Dataset**: pii_validation_dataset.json (31 examples)
**Target**: http://127.0.0.1:8004

## Methodology

- Each example is a text with a ground-truth list of expected PII entities.
- Detection is performed via `POST /api/scan?dry_run=true` (no anonymization).
- **TP** (true positive): expected entity found with matching type and value (substring tolerance).
- **FP** (false positive): detected entity of a known type that has no matching expected entity.
- **FN** (false negative): expected entity not found in detection results.
- **Precision** = TP / (TP + FP) — accuracy of positives.
- **Recall** = TP / (TP + FN) — coverage of ground truth.
- **F1** = 2·P·R / (P + R) — harmonic mean.

## Overall metrics (all languages)

| Entity type | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| codice_fiscale_it | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| credit_card | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| date_of_birth | 0 | 0 | 2 | 0.00 | 0.00 | 0.00 |
| dni_es | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| email | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| iban | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| ipv4 | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| nie_es | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| passport_generic | 0 | 0 | 1 | 0.00 | 0.00 | 0.00 |
| person_name | 14 | 0 | 1 | 1.00 | 0.93 | 0.97 |
| phone_international | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| siret_fr | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| ssn_fr | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| ssn_us | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| steuer_id_de | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| **ALL** | **35** | **0** | **4** | **1.00** | **0.90** | **0.95** |

## Per-language breakdown

### Language: `de`

| Entity type | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| email | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| iban | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| person_name | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| phone_international | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| steuer_id_de | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |

### Language: `en`

| Entity type | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| credit_card | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| date_of_birth | 0 | 0 | 1 | 0.00 | 0.00 | 0.00 |
| email | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| ipv4 | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| passport_generic | 0 | 0 | 1 | 0.00 | 0.00 | 0.00 |
| person_name | 4 | 0 | 1 | 1.00 | 0.80 | 0.89 |
| phone_international | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| ssn_us | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |

### Language: `es`

| Entity type | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| dni_es | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| email | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| nie_es | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| person_name | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| phone_international | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |

### Language: `fr`

| Entity type | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| credit_card | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| date_of_birth | 0 | 0 | 1 | 0.00 | 0.00 | 0.00 |
| email | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| iban | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| person_name | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| phone_international | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| siret_fr | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| ssn_fr | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |

### Language: `it`

| Entity type | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| codice_fiscale_it | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| person_name | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |

## Missed detections (sample)

- `en` — 'Contact John Smith at john.smith@example.com for details.'
  - missing **person_name** = `John Smith`

- `en` — 'Patient SSN: 123-45-6789 was admitted on 14/02/1985.'
  - missing **date_of_birth** = `14/02/1985`

- `en` — "Ms Taylor's passport AB1234567 is valid until 2030."
  - missing **passport_generic** = `AB1234567`

- `fr` — 'Mlle Bernard est nee le 05/08/1990 a Paris.'
  - missing **date_of_birth** = `05/08/1990`