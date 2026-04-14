# MAXIA Oracle — Terms of Service

**Version 1.0 — Effective 14 April 2026**

These Terms of Service ("Terms") govern the use of the MAXIA Oracle API
and all related endpoints (the "Service") operated by MAXIA Oracle
("MAXIA Oracle", "we", "us"). By accessing or using the Service, whether
manually or through any automated agent, you ("User") agree to be bound
by these Terms.

---

## 1. Nature of the Service — Business-to-Business / Business-to-Agent only

MAXIA Oracle is a multi-source price data feed distributed as an API,
designed to be consumed by developers, businesses, and autonomous AI agents
for technical integration. **This Service is exclusively provided to
businesses, developers, and autonomous agents. It is not intended for,
offered to, or designed for individual consumers.** Any use by a natural
person acting outside of a professional capacity is expressly excluded.

The Service is strictly a **data feed**. It aggregates publicly available
price information from multiple upstream sources (Pyth Network, Chainlink,
CoinGecko, CoinPaprika, Yahoo Finance and others) and exposes it through a
unified HTTP interface.

MAXIA Oracle operates in **direct-sale mode**: Users pay a fixed USDC
amount directly to MAXIA Oracle's public treasury wallet on Base mainnet
in exchange for data served through the Service. **There is no
intermediation, no escrow, no custody, and no multi-party settlement.**
The Service never holds, manages, or transmits funds on behalf of any
third party.

## 2. No investment advice

**The data served by the Service is provided for informational and
technical purposes only.** It does not constitute, and must not be
construed as, investment advice, financial advice, a recommendation, a
solicitation to buy or sell any asset, or any form of regulated financial
service.

MAXIA Oracle is not a registered investment advisor, broker-dealer,
financial institution, or securities exchange. No information returned by
the Service should be relied upon as the sole basis for any financial,
investment, trading, or economic decision. Users must conduct their own
research and consult qualified professionals before making any decision
based on information obtained through the Service.

**MAXIA ORACLE EXPRESSLY DISCLAIMS ANY RESPONSIBILITY FOR FINANCIAL
DECISIONS MADE BY USERS OR BY AI AGENTS ACTING ON THEIR BEHALF, WHETHER OR
NOT SUCH DECISIONS WERE INFORMED BY DATA RETURNED BY THE SERVICE.**

## 3. No custody

MAXIA Oracle does not provide custody services of any kind. Specifically:

- The Service does not hold, store, or manage funds, crypto-assets, or
  securities on behalf of Users.
- The Service does not issue, redeem, swap, bridge, or convert
  crypto-assets.
- Payment received via the x402 protocol is a direct peer-to-peer transfer
  from the User's wallet to MAXIA Oracle's public treasury address. No
  third-party account, no trust account, no omnibus account is involved.
- The private key controlling the treasury wallet is never stored on any
  server operated by MAXIA Oracle. Treasury funds are withdrawn manually
  to cold storage on a regular basis.

## 4. No KYC, no identity collection

MAXIA Oracle does not perform Know-Your-Customer ("KYC") or
Know-Your-Business ("KYB") checks. The Service does not collect, store,
or process any identity document, tax identifier, or personal information
about Users. Authentication is performed via either:

- an opaque API key ("X-API-Key") generated server-side on request and
  linked only to usage counters, never to an identity; or
- an on-chain x402 payment, which exposes only the sender's public wallet
  address (already public on the blockchain) and nothing else.

Users who wish to remain pseudonymous are free to do so.

## 5. Payment terms

### 5.1 — Pricing

The price per API call is published in the Service's documentation and
may be updated in accordance with Section 10. As of the effective date
of these Terms, the prices are:

- **Single price query** (`GET /api/price/{symbol}`): 0.001 USDC per call
- **Batch price query** (`POST /api/prices/batch`): 0.005 USDC per call,
  up to 50 symbols per request

The free tier, accessible via a self-issued API key, grants 100 calls per
calendar day at no cost. Beyond the free tier quota, a valid x402 payment
is required for anonymous pay-per-call access.

### 5.2 — Payment method and finality

Payments are settled in USDC on Base mainnet (chain ID 8453) via the
**x402 protocol** developed by Coinbase. The USDC contract address is
`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (canonical Base USDC).

**All payments are final and non-refundable.** Blockchain transactions
are irrevocable by design: once a USDC transfer reaches the MAXIA Oracle
treasury wallet, it cannot be reversed by MAXIA Oracle, by the User, or
by any third party.

### 5.3 — Replay protection

Each payment is identified by its on-chain transaction hash. The Service
records every successfully verified transaction hash and will reject any
subsequent request reusing the same hash. Users must therefore submit a
fresh on-chain payment for each paid API call.

## 6. No refund

Given the technical nature of the Service (real-time data feed with a
marginal cost tending to zero, and blockchain-final payment), **MAXIA
Oracle does not offer refunds**.

In the exceptional case of a verified Service failure — i.e., a request
for which MAXIA Oracle received a valid payment but failed to return the
contracted data due to a reproducible server-side error — MAXIA Oracle
**may, at its sole and absolute discretion**, issue a goodwill credit in
the form of free future API calls. This is a discretionary commercial
gesture, not a contractual obligation. MAXIA Oracle is under no
obligation to issue any credit, cash refund, or compensation.

## 7. Limitation of liability

**TO THE FULLEST EXTENT PERMITTED BY APPLICABLE LAW, MAXIA ORACLE'S TOTAL
CUMULATIVE LIABILITY TO ANY USER FOR ANY CLAIM ARISING OUT OF OR RELATED
TO THESE TERMS OR THE SERVICE, WHETHER IN CONTRACT, TORT, NEGLIGENCE,
STRICT LIABILITY, OR ANY OTHER LEGAL THEORY, SHALL NOT EXCEED THE TOTAL
AMOUNT ACTUALLY PAID BY THE USER TO MAXIA ORACLE FOR THE SPECIFIC API
CALL GIVING RISE TO THE CLAIM** (typically 0.001 USDC per single-price
query or 0.005 USDC per batch query).

**MAXIA ORACLE SHALL IN NO EVENT BE LIABLE FOR ANY INDIRECT, INCIDENTAL,
CONSEQUENTIAL, SPECIAL, EXEMPLARY, OR PUNITIVE DAMAGES, INCLUDING BUT NOT
LIMITED TO LOST PROFITS, LOST REVENUE, LOST TRADING OPPORTUNITIES,
TRADING LOSSES, OR DAMAGES RESULTING FROM FINANCIAL DECISIONS TAKEN ON
THE BASIS OF DATA RETURNED BY THE SERVICE, EVEN IF MAXIA ORACLE HAS BEEN
ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.**

The Service is provided "AS IS" and "AS AVAILABLE", without warranty of
any kind, express or implied, including without limitation warranties of
merchantability, fitness for a particular purpose, accuracy,
completeness, timeliness, non-infringement, or uninterrupted operation.

## 8. Privacy and confidentiality

MAXIA Oracle does not track Users and does not retain personal data:

- No persistent IP address logging beyond seven (7) days
- No cookies, no tracking pixels, no analytics fingerprinting
- No identity information tied to API keys or wallet addresses
- No transmission of usage data to third-party analytics providers

Server logs are kept for a maximum of 7 days solely for the purpose of
operational troubleshooting and abuse mitigation, after which they are
permanently deleted.

## 9. Contractual party for autonomous agents

Where the Service is accessed by an autonomous agent or automated
software (including but not limited to AI agents, trading bots, scraping
tools, or any non-human user), **the natural or legal person controlling
the wallet used for payment, and/or the natural or legal person who
deployed, configured, or operates the agent, is deemed to have accepted
these Terms in their own name**. The agent itself is not a contractual
party; it is a technical instrument of its principal. The principal is
solely responsible for the agent's compliance with these Terms.

## 10. Governing law and jurisdiction

These Terms are governed by and construed in accordance with the laws of
France, without regard to its conflict of law provisions or to any rule
that would apply the law of another jurisdiction.

**ANY DISPUTE, CONTROVERSY, OR CLAIM ARISING OUT OF OR RELATING TO THESE
TERMS, OR THE BREACH, TERMINATION, VALIDITY, INTERPRETATION, OR
PERFORMANCE THEREOF, SHALL BE SUBMITTED TO THE EXCLUSIVE JURISDICTION OF
THE COMPETENT COURTS OF TOULOUSE, FRANCE.**

This exclusive jurisdiction clause applies even in the case of multiple
defendants, third-party claims, interim or emergency proceedings,
class-action claims, and actions for preliminary or conservatory
measures, to the fullest extent permitted by French law.

The parties hereby expressly acknowledge that this clause has been
negotiated in a business-to-business context between commercial parties
and meets the "specified in a very apparent manner" requirement of
Article 48 of the French Code of Civil Procedure.

## 11. Modifications of these Terms

MAXIA Oracle reserves the right to modify these Terms at any time. Any
material modification will be notified through the Service's official
documentation URL (`oracle.maxiaworld.app/terms` or successor URL) at
least thirty (30) calendar days before the modification takes effect.
Continued use of the Service after the effective date of the modified
Terms constitutes acceptance of the modified Terms.

## 12. Entire agreement — Severability

These Terms constitute the entire agreement between the User and MAXIA
Oracle regarding the Service and supersede any prior agreement,
understanding, or communication, whether written or oral.

If any provision of these Terms is held to be invalid, illegal, or
unenforceable by a court of competent jurisdiction, such provision shall
be severed from these Terms and the remaining provisions shall continue
in full force and effect.

## 13. Contact

For legal inquiries regarding these Terms, contact:
`legal@maxiaworld.app` (or successor contact address published at
`oracle.maxiaworld.app`).

---

*MAXIA Oracle — Data feed only. Not investment advice. No custody. No KYC.*
