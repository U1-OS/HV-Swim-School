# HV Swim Bendigo V5.10 security verification

Verified locally on 30 August 2026 against the V5.10 source and a running development server.
This is an engineering baseline, not a claim that the service is unhackable and not a
replacement for an independent production penetration test.

## Result

- Full Python/API/security suite: 114 passed, 1 skipped.
- Static website consistency check: 19 pages, 14 service-worker files and 8 scripts passed.
- Live HTTP security baseline: 20/20 checks passed.
- JavaScript syntax, Python compilation and Git whitespace checks passed.

## Controls exercised

- Unauthenticated access was denied for family, staff and management APIs.
- Role and family-ownership boundaries were tested for swimmers, incident reports, staff
  records, integrations and administrative workflows.
- Incident narratives and child health/safety fields were verified as ciphertext at rest;
  sensitive text was also verified absent from audit details.
- Session cookies, one-way session-token storage, CSRF enforcement, rate limits and password
  hashing were covered by the automated suite.
- The live server returned Content-Security-Policy, clickjacking, MIME-sniffing, referrer and
  cross-origin opener controls.
- Requests for `.env`, the SQLite database, backend source and `.git` data returned 404.
- TRACE, unexpected form bodies, oversized JSON, SQL-injection login input and untrusted CORS
  origins failed closed.
- The paused app routes returned 404.
- Staff clock requests were verified without browser geolocation, GPS coordinates or
  continuous device tracking.
- Payment boundaries were reviewed: lesson charges create Xero-bound records; merchandise
  remains non-orderable until approved Shopify catalogue and checkout configuration are live.

## Remaining production work

- Replace SQLite with managed PostgreSQL, use an Australian-region HTTPS deployment, private
  secret storage, encrypted backups, tested restore procedures and production monitoring.
- Complete MFA, password recovery, account deletion/session management and provider webhook
  verification before accepting real family, child, payroll or payment-related data.
- Commission an independent penetration test and privacy/legal/accessibility reviews against
  the final deployed infrastructure and real configuration.
- Complete live Xero contact/invoice reconciliation and Shopify customer/catalogue/checkout
  mappings with idempotency and sandbox-to-live acceptance tests.
- Keep dependency advisories and the FastAPI/Starlette compatibility exceptions documented in
  `SECURITY.md` under active review.
