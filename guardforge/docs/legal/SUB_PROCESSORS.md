# GuardForge Sub-processor List

**Effective:** 2026
**Last updated:** 2026

This page lists all third-party sub-processors that may process Personal Data on behalf of MAXIA Lab in the context of providing GuardForge to customers using the Cloud Edition.

For the Self-Hosted Edition, no sub-processors are involved — the customer is the sole operator and controls all infrastructure.

---

## Current sub-processors (Cloud Edition only)

| Provider | Service provided | Data processed | Location | Safeguards |
|---|---|---|---|---|
| **OVH SAS** | Cloud infrastructure (VPS, storage, network) | All Cloud Edition data: API requests, audit logs, vault secrets | France (Paris) and Germany (Frankfurt) | EU-based, GDPR-compliant by default. ISO 27001 certified. |
| **LemonSqueezy Inc.** | Payment processing, subscription billing, license key issuance | Customer billing details (name, email, address, payment method via Stripe) | Wyoming, USA | Standard Contractual Clauses (SCCs). PCI-DSS compliant. Used for Cloud Edition subscriptions and Self-Hosted licenses. |
| **Cloudflare, Inc.** | DNS, CDN, DDoS protection (when enabled) | Request metadata (IP, User-Agent, headers) | Global edge network with EU presence | Standard Contractual Clauses (SCCs). GDPR-compliant cookie-less analytics. |

---

## How sub-processors are selected

We select sub-processors based on:

1. **Data protection compliance** — GDPR, ISO 27001, SOC 2 where applicable
2. **Geographic location** — EU/EEA preferred for primary processing
3. **Security posture** — Encryption at rest and in transit, audit logs, incident response
4. **Operational reliability** — Uptime SLA, support quality
5. **Contractual safeguards** — DPA in place, SCCs for international transfers

---

## Notification of changes

We will notify customers of any intended changes to this list (addition, replacement, or removal of a sub-processor) at least **30 days in advance**, via:

- Email to the primary administrator account on file
- Update to this page
- Notice in the dashboard `/compliance` section

Customers may object to a change on reasonable grounds within 14 days of notification. In such cases, MAXIA Lab will work in good faith to find an alternative or, if no alternative is feasible, allow the customer to terminate the affected portion of the Service without penalty.

---

## Self-Hosted Edition

The Self-Hosted Edition has **zero sub-processors**. The customer is the sole operator of GuardForge in this deployment model. MAXIA Lab does not have access to data processed by Self-Hosted instances.

The only network communication initiated by Self-Hosted GuardForge to MAXIA Lab is the **license phone-home component**, which transmits only:

- License key hash
- Software version
- Instance identifier (random UUID generated at install time)
- Heartbeat timestamp

No customer data, no scan content, no PII, no metrics. The phone-home runs once every 24 hours and is documented in the License Agreement (Section 5).

---

## Historical changes

| Date | Change |
|---|---|
| 2026-01 | Initial sub-processor list published |

---

## Contact

For questions about sub-processors, data location, or to request additional information:

**Email**: privacy@maxialab.com _(coming soon — use contact@maxialab.com in the meantime)_
