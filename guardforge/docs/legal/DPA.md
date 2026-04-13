# Data Processing Agreement (DPA)

**Between:** [Customer Legal Name] ("Controller")
**And:** MAXIA Lab, [legal address] ("Processor")
**Service:** GuardForge ("the Service")
**Effective:** [Date]
**Version:** 1.0

This Data Processing Agreement ("DPA") forms an integral part of the GuardForge License Agreement and Terms of Service. It governs the processing of Personal Data by the Processor on behalf of the Controller in the context of the Service. This DPA is drafted to comply with Article 28 of Regulation (EU) 2016/679 (GDPR).

---

## 1. Definitions

- **"Personal Data"** means any information relating to an identified or identifiable natural person, as defined in Article 4(1) GDPR.
- **"Processing"** means any operation performed on Personal Data, as defined in Article 4(2) GDPR.
- **"Data Subject"** means an identified or identifiable natural person to whom Personal Data relates.
- **"Sub-processor"** means any third party engaged by the Processor to assist with Processing under this DPA.
- **"Personal Data Breach"** means a breach of security leading to the accidental or unlawful destruction, loss, alteration, unauthorized disclosure of, or access to, Personal Data.

## 2. Roles and Scope

The Controller appoints the Processor to process Personal Data on its behalf for the sole purpose of providing the Service as described in the License Agreement. The Processor shall not process Personal Data for any other purpose.

The Controller remains the sole data controller and is responsible for the lawfulness of the Processing under applicable data protection laws.

## 3. Nature, Purpose, and Duration

| Item | Description |
|---|---|
| **Nature of Processing** | Detection, anonymization, tokenization, and storage of Personal Data submitted by the Controller via API calls or dashboard usage. |
| **Purpose** | Enable the Controller to detect and remove Personal Data from text before transmitting to third-party LLM providers, in compliance with applicable data protection laws. |
| **Categories of Data Subjects** | End users, customers, or contacts of the Controller whose data is submitted to the Service. |
| **Categories of Personal Data** | Names, email addresses, phone numbers, financial identifiers (IBAN, credit card, etc.), national identifiers (SSN, SIRET, DNI, etc.), and any text content submitted to the Service. |
| **Special Categories** | Health data may be processed if the Controller uses the Service for HIPAA workloads. The Controller is responsible for obtaining the necessary legal basis. |
| **Duration** | For the duration of the License Agreement and any retention period specified by the Controller. |

## 4. Processor Obligations

The Processor agrees to:

(a) **Process Personal Data only on documented instructions** from the Controller, including with regard to transfers to third countries, unless required by applicable law.

(b) **Ensure that persons authorized to process Personal Data** have committed themselves to confidentiality or are under a statutory obligation of confidentiality.

(c) **Implement appropriate technical and organizational measures** to ensure a level of security appropriate to the risk, including:
- AES-256 encryption (Fernet) of stored secrets and tokenization mappings
- TLS 1.2+ for all data in transit
- Access control with role-based permissions
- Audit logging of all data access
- Rate limiting and DDoS protection
- Regular security updates and patch management

(d) **Assist the Controller** in fulfilling its obligation to respond to requests from Data Subjects to exercise their rights (access, rectification, erasure, restriction, portability, objection).

(e) **Assist the Controller in ensuring compliance** with the obligations under Articles 32-36 GDPR (security, breach notification, impact assessment, prior consultation).

(f) **Notify the Controller without undue delay** (and in any case within 72 hours) after becoming aware of a Personal Data Breach.

(g) **Make available to the Controller** all information necessary to demonstrate compliance with this DPA, and allow for and contribute to audits, including inspections, conducted by the Controller or another auditor mandated by the Controller.

(h) **At the choice of the Controller**, delete or return all Personal Data after the end of the provision of services, and delete existing copies unless legal obligations require otherwise.

## 5. Sub-processors

The Controller authorizes the Processor to engage Sub-processors for the provision of the Service. The current list of Sub-processors is available in `docs/legal/SUB_PROCESSORS.md` and may be updated by the Processor.

The Processor shall:
- Inform the Controller of any intended changes concerning the addition or replacement of Sub-processors at least 30 days in advance.
- Impose data protection obligations on Sub-processors that are no less protective than those set out in this DPA.
- Remain fully liable to the Controller for the performance of any Sub-processor.

The Controller may object to the addition or replacement of a Sub-processor on reasonable grounds within 14 days of notification.

## 6. International Transfers

For Cloud Edition users, Personal Data is processed in the European Union (Frankfurt and Paris data centers, OVH). No transfers outside the EU/EEA are made by default.

If a transfer outside the EU/EEA is required, the Processor shall ensure that:
- The destination country has an adequacy decision under Article 45 GDPR, OR
- Standard Contractual Clauses (SCCs) approved by the European Commission are in place, OR
- Other appropriate safeguards under Articles 46-49 GDPR are implemented.

For Self-Hosted Edition users, the Controller is responsible for the location of Processing.

## 7. Security Measures

The Processor implements and maintains the technical and organizational measures detailed in `docs/legal/SECURITY_WHITEPAPER.md`. These measures include but are not limited to:

- **Encryption**: AES-256 at rest, TLS 1.2+ in transit
- **Access control**: API key authentication, role-based access (where applicable)
- **Audit logging**: All scan operations logged with timestamp, hash, action, and policy
- **Network security**: Rate limiting, CORS restrictions, security headers
- **Vulnerability management**: Regular dependency audits, security patches
- **Data minimization**: Input text is hashed (SHA-256) before storage; raw text is never persisted

## 8. Data Subject Rights

The Processor shall provide reasonable assistance to the Controller, at the Controller's expense, to enable the Controller to respond to Data Subject requests within the legal timeframes. The Processor shall not respond directly to Data Subjects unless authorized by the Controller or required by law.

## 9. Personal Data Breach Notification

In the event of a Personal Data Breach affecting the Controller's data, the Processor shall:

(a) Notify the Controller without undue delay and in any case within 72 hours of becoming aware.

(b) Provide at least the following information:
- The nature of the breach
- The categories and approximate number of Data Subjects affected
- The categories and approximate number of Personal Data records affected
- The likely consequences
- The measures taken or proposed to address the breach

(c) Cooperate with the Controller in any investigation, remediation, and notification to supervisory authorities and Data Subjects as required.

## 10. Audit Rights

The Controller has the right to audit the Processor's compliance with this DPA, at the Controller's expense, no more than once per calendar year, with at least 30 days' written notice. The Processor shall provide reasonable cooperation.

The Processor may satisfy this obligation by providing the Controller with up-to-date third-party audit reports (e.g., SOC 2 Type II) when available.

## 11. Liability

Each party's liability under this DPA is limited as set out in the License Agreement. The Processor's total liability for any claim arising from this DPA shall not exceed the fees paid by the Controller in the twelve months preceding the event giving rise to the claim.

## 12. Termination

This DPA terminates automatically upon termination of the License Agreement. Upon termination, the Processor shall, at the Controller's choice, delete or return all Personal Data within 30 days, except where retention is required by law.

## 13. Governing Law

This DPA is governed by the laws of France, without prejudice to mandatory provisions of EU data protection law. Any dispute shall be subject to the exclusive jurisdiction of the courts of Paris, France.

## 14. Entire Agreement

This DPA supersedes any prior data processing agreement between the parties and constitutes the entire agreement regarding the Processing of Personal Data under the Service.

---

**Signatures**

For the Controller:
Name: ________________________________
Title: ________________________________
Date: ________________________________
Signature: ____________________________

For the Processor (MAXIA Lab):
Name: ________________________________
Title: ________________________________
Date: ________________________________
Signature: ____________________________

---

*This DPA is a draft template provided for informational purposes. It is not legal advice. Customers are advised to have it reviewed by their own legal counsel before signature, particularly for enterprise deployments involving sensitive data or specific regulatory regimes (HIPAA, EU AI Act, etc.).*
