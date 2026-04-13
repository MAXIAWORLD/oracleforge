# GuardForge Terms of Service

**Effective date:** [Date]
**Last updated:** 2026
**Version:** 1.0

These Terms of Service ("Terms") govern your access to and use of GuardForge (the "Service"), provided by MAXIA Lab ("we", "us", "our"). By accessing or using the Service, you agree to be bound by these Terms. If you do not agree, you must not use the Service.

---

## 1. Acceptance of terms

By creating an account, downloading the Self-Hosted Edition, or using the Cloud Edition, you confirm that:

(a) You are at least 18 years old or have legal capacity in your jurisdiction.
(b) You have authority to enter into this agreement on behalf of your organization (if applicable).
(c) You have read and accept these Terms, our Privacy Policy, and the License Agreement.

---

## 2. The Service

GuardForge is a software service for detecting, redacting, and tokenizing personally identifiable information (PII) in text, primarily intended to prevent PII leakage to large language model (LLM) providers.

The Service is offered in two editions:

- **Cloud Edition** — Hosted by MAXIA Lab, accessed via subscription
- **Self-Hosted Edition** — Installed and operated by you on your own infrastructure, licensed via one-time payment

---

## 3. Account creation (Cloud Edition)

To use the Cloud Edition, you must create an account by providing:
- A valid email address
- A password (or OAuth credentials)
- Billing information for paid tiers

You are responsible for:
- Maintaining the confidentiality of your account credentials
- All activities that occur under your account
- Notifying us immediately of any unauthorized access

---

## 4. Acceptable use

You agree to use the Service only for lawful purposes and in accordance with these Terms. You will NOT:

(a) Use the Service in violation of any applicable law or regulation, including data protection laws.

(b) Submit content that infringes intellectual property rights, contains malware, or is otherwise illegal.

(c) Attempt to gain unauthorized access to the Service, other accounts, or our infrastructure.

(d) Reverse-engineer, decompile, or disassemble the Service except as permitted by law.

(e) Use the Service to develop a competing product or service.

(f) Resell, sublicense, or redistribute the Service or your access to it.

(g) Exceed the rate limits, scan quotas, or other usage limits of your subscription tier.

(h) Use the Service to scan content you do not have the right to process.

(i) Use automated tools to scrape, crawl, or download data from the Service except via our published API.

(j) Use the Service in a manner that disrupts, degrades, or impairs its operation for other users.

Violations may result in immediate suspension or termination of your account without refund.

---

## 5. Subscription, billing, and cancellation (Cloud Edition)

### 5.1 Subscription tiers

Available tiers and pricing are listed at https://maxialab.com/guardforge/pricing _(coming soon)_. Quotas, features, and prices are subject to change with 30 days' notice for existing subscribers.

### 5.2 Billing

- Subscriptions are billed monthly or annually in advance, depending on your selection
- Payments are processed by LemonSqueezy
- All fees are exclusive of applicable taxes
- Failed payments may result in service suspension after 7 days of non-payment

### 5.3 Cancellation

- You may cancel your subscription at any time from the dashboard or by contacting support
- Cancellation takes effect at the end of the current billing period
- No prorated refunds for partial periods

### 5.4 Refunds

- New subscribers may request a full refund within 14 days of purchase ("cooling-off period") for any reason
- After the cooling-off period, refunds are at our sole discretion

### 5.5 Free tier

- The Free tier may be used indefinitely subject to its quota limits
- We reserve the right to modify Free tier limits with 30 days' notice
- We may suspend Free accounts that have been inactive for 12 months or more

---

## 6. Self-Hosted Edition specific terms

- The Self-Hosted Edition is licensed via one-time payment for perpetual use within the limits of your purchased tier (number of instances, etc.)
- Updates and upgrades are included for the period specified at purchase (typically 6, 12, or 24 months)
- A phone-home component validates your license periodically; disabling it constitutes a material breach
- See the LICENSE file for full terms

---

## 7. Intellectual property

### 7.1 Our property

The Service, including all software, algorithms, designs, documentation, trademarks, and content created by MAXIA Lab, is and remains our exclusive property and is protected by copyright, trademark, and other intellectual property laws.

### 7.2 Your content

You retain all rights to the text and data you submit to the Service ("Your Content"). By submitting Your Content, you grant us a limited, non-exclusive, royalty-free license to process Your Content solely for the purpose of providing the Service to you.

We do NOT use Your Content to train AI models or for any purpose other than providing the Service.

### 7.3 Feedback

If you provide feedback, suggestions, or ideas about the Service, you grant us a perpetual, irrevocable, royalty-free license to use them without obligation to you.

---

## 8. Service availability

### 8.1 Uptime targets

| Tier | Uptime target |
|---|---|
| Free | Best effort |
| Starter / Pro | 99.5% monthly |
| Business | 99.9% monthly |
| Enterprise | 99.95% monthly (SLA-backed) |

### 8.2 Maintenance

We may perform scheduled maintenance with at least 24 hours' notice. Emergency maintenance may occur without notice.

### 8.3 No guarantee

The Service is provided "as is" and "as available" without warranty of any kind. See Section 11 for the full disclaimer.

---

## 9. Data and privacy

Your use of the Service is also governed by our Privacy Policy and, where applicable, our Data Processing Agreement (DPA). See `docs/legal/PRIVACY_POLICY.md` and `docs/legal/DPA.md`.

Key points:
- We do NOT store raw text submitted to scans (only SHA-256 hashes)
- Vault data is encrypted with AES-256
- Cloud Edition data is processed in the EU (Frankfurt, Paris)
- We do NOT sell your data or share it for advertising

---

## 10. Termination

### 10.1 Termination by you

You may terminate this agreement at any time by cancelling your subscription (Cloud) or ceasing use (Self-Hosted).

### 10.2 Termination by us

We may suspend or terminate your account immediately if:
- You materially breach these Terms
- You fail to pay applicable fees
- You engage in fraudulent or illegal activity
- We discontinue the Service (with at least 90 days' notice)

### 10.3 Effect of termination

Upon termination:
- Your right to use the Service ends immediately
- We will retain your data per the retention schedule in our Privacy Policy
- You may export your data within 30 days of termination
- Sections 7 (IP), 11 (warranty disclaimer), 12 (liability), 13 (indemnification), and 14 (governing law) survive

---

## 11. Warranty disclaimer

THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.

WE DO NOT WARRANT THAT:
- THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE
- ALL PII WILL BE DETECTED IN ALL CASES (PII DETECTION IS A BEST-EFFORT FEATURE BASED ON HEURISTICS)
- THE SERVICE WILL MEET YOUR SPECIFIC REQUIREMENTS
- ANY ERRORS WILL BE CORRECTED

YOU REMAIN SOLELY RESPONSIBLE FOR YOUR OWN COMPLIANCE WITH APPLICABLE DATA PROTECTION LAWS. THE SERVICE IS A TOOL TO ASSIST WITH COMPLIANCE, NOT A SUBSTITUTE FOR A COMPLETE COMPLIANCE PROGRAM.

---

## 12. Limitation of liability

TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW:

(a) IN NO EVENT SHALL MAXIA LAB BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOSS OF PROFITS, DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES.

(b) OUR TOTAL CUMULATIVE LIABILITY UNDER THESE TERMS SHALL NOT EXCEED THE FEES PAID BY YOU TO US IN THE TWELVE (12) MONTHS PRECEDING THE EVENT GIVING RISE TO THE CLAIM.

(c) WE ARE NOT LIABLE FOR ANY REGULATORY FINES, PENALTIES, OR ENFORCEMENT ACTIONS YOU MAY INCUR AS A RESULT OF USING (OR FAILING TO USE) THE SERVICE.

Some jurisdictions do not allow the exclusion of certain warranties or limitations of liability. In such jurisdictions, our liability is limited to the maximum extent permitted by law.

---

## 13. Indemnification

You agree to indemnify, defend, and hold harmless MAXIA Lab from and against any claims, damages, losses, liabilities, and expenses (including reasonable attorneys' fees) arising out of or related to:

(a) Your use of the Service in violation of these Terms
(b) Your violation of any law or regulation
(c) Your violation of any third-party rights
(d) Content you submit to the Service

---

## 14. Governing law and dispute resolution

These Terms are governed by the laws of France, without regard to conflict of laws principles. Any dispute arising out of or in connection with these Terms shall be subject to the exclusive jurisdiction of the courts of Paris, France.

For consumers in the European Union, this choice of law does not deprive you of the protection of mandatory consumer protection laws of your country of residence.

---

## 15. Changes to these terms

We may update these Terms from time to time. Material changes will be communicated by:
- Email to the primary account email
- Notice in the dashboard
- Update to the "Last updated" date

Continued use after the effective date of changes constitutes acceptance. If you do not agree to the new Terms, you must stop using the Service.

---

## 16. Miscellaneous

### 16.1 Entire agreement
These Terms, together with the Privacy Policy, License Agreement, and any applicable DPA, constitute the entire agreement between you and MAXIA Lab regarding the Service.

### 16.2 Severability
If any provision of these Terms is found to be unenforceable, the remaining provisions shall remain in full force and effect.

### 16.3 No waiver
Our failure to enforce any right or provision of these Terms shall not constitute a waiver.

### 16.4 Assignment
You may not assign these Terms without our prior written consent. We may assign these Terms freely, including in the event of a merger or acquisition.

### 16.5 Notices
We may send you notices via email to the address on file. You may contact us at contact@maxialab.com.

### 16.6 Force majeure
Neither party shall be liable for failure to perform due to causes beyond reasonable control (natural disasters, war, pandemics, government actions, etc.).

---

## 17. Contact

For questions about these Terms:

**Email**: contact@maxialab.com
**Address**: [Legal address]

For privacy-related inquiries: privacy@maxialab.com (coming soon)
For security reports: security@maxialab.com (coming soon)

---

*These Terms of Service are a draft template provided for informational purposes. They are not legal advice. We recommend having them reviewed by qualified legal counsel before relying on them, particularly for enterprise deployments and jurisdictions with specific consumer protection requirements.*
