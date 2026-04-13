# GuardForge Privacy Policy

**Effective date:** [Date]
**Last updated:** 2026
**Version:** 1.0

This Privacy Policy describes how MAXIA Lab ("we", "us", "our") collects, uses, and protects personal information when you use the GuardForge service (the "Service"). We are committed to protecting your privacy and complying with applicable data protection laws including the General Data Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and other regional privacy laws.

---

## 1. Who we are

**Data Controller:** MAXIA Lab
**Address:** [Legal address]
**Contact:** privacy@maxialab.com _(coming soon — use contact@maxialab.com in the meantime)_

For inquiries related to data protection or to exercise your rights, please contact us using the email above.

---

## 2. Personal data we collect

We collect the following categories of personal data:

### 2.1 Account information
- Name
- Email address
- Company name (optional)
- Billing address
- Payment method (processed by our sub-processor LemonSqueezy)

### 2.2 Usage data
- API requests (count, timestamp, endpoint)
- Dashboard interactions (page views, language preference)
- IP address
- Browser type and version
- Device type

### 2.3 Service data
**Important**: When you use the Service to scan text for PII, **we do NOT store the raw text**. Only the following is persisted:
- A SHA-256 hash of the input (first 16 characters) — irreversible
- Count of PII items detected
- Types of PII detected (e.g., "email", "credit_card") — categorical, not specific values
- The action taken (block / anonymize / warn / tokenize)
- The policy applied
- Timestamp

### 2.4 Vault data (Cloud Edition)
If you use the vault feature to store secrets or tokenization mappings:
- The keys you choose
- The encrypted values (encrypted with AES-256 Fernet using your account's master key)
- We never have access to the plaintext values

### 2.5 Communications
- Support email content
- Survey responses
- Feedback submitted through the dashboard

---

## 3. How we use personal data

We use personal data for the following purposes:

| Purpose | Legal basis (GDPR Art. 6) |
|---|---|
| Provide the Service | Performance of contract |
| Process payments | Performance of contract |
| Send service-related notifications (downtime, security advisories, billing) | Performance of contract |
| Respond to support requests | Performance of contract |
| Improve the Service (analytics, debugging) | Legitimate interest |
| Comply with legal obligations (tax, accounting, audit) | Legal obligation |
| Marketing communications (only with explicit opt-in) | Consent |

---

## 4. Sharing of personal data

We share personal data with:

### 4.1 Sub-processors
See `SUB_PROCESSORS.md` for the full list. Currently:
- **OVH** (cloud infrastructure, EU)
- **LemonSqueezy** (payment processing, USA)
- **Cloudflare** (DDoS protection, global)

All sub-processors are bound by Data Processing Agreements and provide appropriate safeguards.

### 4.2 Legal authorities
We may disclose personal data if required by law, court order, or to protect our rights and property.

### 4.3 Acquirers
In the event of a merger, acquisition, or sale of assets, your data may be transferred to the acquiring entity. You will be notified in advance.

### 4.4 We do NOT
- Sell your personal data
- Share it for advertising purposes
- Use it to train AI models

---

## 5. International transfers

For Cloud Edition users, your data is processed in the **European Union** (Frankfurt and Paris data centers). We do not transfer data outside the EU/EEA by default.

When transfers are necessary (e.g., LemonSqueezy in the USA for payments), we use **Standard Contractual Clauses (SCCs)** approved by the European Commission as the legal basis.

For Self-Hosted Edition users, you control where your data is processed.

---

## 6. Data retention

| Data type | Retention period |
|---|---|
| Account information | For the duration of your subscription + 6 years (legal/tax) |
| Audit logs (Cloud Free / Starter) | 30 days |
| Audit logs (Cloud Pro) | 1 year |
| Audit logs (Cloud Business / Enterprise) | Unlimited (or per customer request) |
| Vault data | Until you delete it OR 30 days after subscription cancellation |
| Support communications | 3 years |
| Marketing data (with consent) | Until you withdraw consent |

After the retention period, data is permanently deleted from our systems and backups within 90 days.

---

## 7. Your rights

Under the GDPR (and similar laws), you have the following rights:

- **Access**: Request a copy of the personal data we hold about you
- **Rectification**: Request correction of inaccurate data
- **Erasure** ("right to be forgotten"): Request deletion of your data
- **Restriction**: Request that we limit processing
- **Portability**: Receive your data in a structured, machine-readable format
- **Objection**: Object to processing based on legitimate interest
- **Withdraw consent**: Where processing is based on consent
- **Complaint**: Lodge a complaint with your local supervisory authority (e.g., CNIL in France)

To exercise any of these rights, contact us at privacy@maxialab.com. We will respond within 30 days.

---

## 8. Security

We implement industry-standard security measures to protect your personal data:

- **Encryption**: AES-256 at rest, TLS 1.2+ in transit
- **Access control**: API key authentication, role-based access
- **Audit logging**: All data access is logged
- **Vulnerability management**: Regular security patches and dependency audits
- **Incident response**: Documented incident response plan with 72-hour breach notification

For more details, see our `SECURITY_WHITEPAPER.md`.

---

## 9. Cookies and tracking

The GuardForge dashboard uses **only essential cookies**:
- Session cookies for authentication
- Theme preference (dark/light)
- Language preference

We do **not** use:
- Tracking cookies
- Third-party analytics (no Google Analytics, no Facebook Pixel)
- Behavioral advertising

---

## 10. Children's privacy

GuardForge is a B2B service intended for businesses. We do not knowingly collect personal data from children under 16. If you believe we have collected such data, please contact us immediately and we will delete it.

---

## 11. Changes to this policy

We may update this Privacy Policy from time to time. We will notify you of material changes by:
- Email to the primary administrator account
- Notice in the dashboard
- Update to the "Last updated" date at the top of this page

Continued use of the Service after the effective date of changes constitutes acceptance.

---

## 12. Jurisdiction-specific provisions

### 12.1 California residents (CCPA / CPRA)

You have the right to:
- Know what personal information is collected, used, shared, or sold
- Delete personal information we hold (subject to exceptions)
- Opt-out of the sale of personal information (we do not sell data)
- Non-discrimination for exercising your rights

### 12.2 EU/EEA residents (GDPR)

You have the rights listed in Section 7 above. You may also lodge a complaint with your national supervisory authority. In France, this is the CNIL (https://www.cnil.fr).

### 12.3 Brazilian residents (LGPD)

You have rights similar to GDPR, including access, rectification, anonymization, portability, and deletion. The data controller representative for Brazil can be contacted at privacy@maxialab.com.

### 12.4 UK residents (UK GDPR)

Your rights are equivalent to those under EU GDPR. You may complain to the Information Commissioner's Office (ICO).

---

## 13. Contact

For privacy-related questions or to exercise your rights:

**Email**: privacy@maxialab.com _(coming soon — use contact@maxialab.com in the meantime)_
**Postal address**: [Legal address]

For general inquiries: contact@maxialab.com

---

*This Privacy Policy is a draft template provided for informational purposes. It is not legal advice. Customers and users are advised to review it with their own legal counsel before relying on it for compliance with specific regulations.*
