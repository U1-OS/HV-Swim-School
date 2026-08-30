# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-31 by Codex — V5.12.0 backend hardening complete

## Current state

V5.12.0 is the verified website and browser-platform release for HV Swim Bendigo. It
preserves the V5.11 premium public experience, role-based portals, Laura-led business
identity, locations and conditions, family safety records, staff operations, merchandise
boundaries and the reviewed Xero lesson-invoice workflow. The native-app phase remains
paused and its public routes remain blocked.

This release is a production-readiness backend pass rather than a visual rebuild. It fixes
the certificate-upload limit mismatch, improves SQLite preview concurrency, separates OAuth
token encryption from session signing, makes finance transitions atomic, distrusts external
provider responses by default and adds a protected operational health endpoint.

## Delivered in V5.12.0

- Fixed the staff certificate upload path: verified PDF/PNG/JPEG/WebP documents can now use
  the documented 5 MB limit while ordinary API requests remain capped at 2 MB. Chunked
  requests cannot bypass the boundary, and incomplete PNG files are rejected.
- Added `X-Request-ID` to every response and production-safe unhandled-error responses with
  correlated server logging. Development still raises exceptions for debugging.
- Hardened the SQLite preview with WAL, foreign-key enforcement, `synchronous=NORMAL` and a
  bounded 15-second busy timeout. Managed PostgreSQL is still required for real production.
- Added authenticated `GET /api/admin/system-health`: database quick check, foreign-key
  violations, billing total mismatches, journal mode, integration-token encryption version
  and Xero/Shopify/weather/sensor readiness without paths, secrets or customer records.
- Introduced versioned authenticated integration-token encryption using the separate
  `HV_DATA_ENCRYPTION_KEY` in production. Legacy V5.11 session-key-encrypted records are
  migrated atomically at startup and the migration is audited.
- Made invoice creation, approval and Xero outbound claiming transactionally serialized.
  Conditional state updates reject duplicate or stale management actions.
- Hardened Xero OAuth refresh and invoice processing: complete tenant/token checks, safe
  expiry parsing, refresh-token preservation, DRAFT-only confirmation, requested invoice-ID
  matching, local/provider total and balance reconciliation, and strict `in.xero.com` HTTPS
  customer-payment links. Unsafe refreshes enter `sync_review` with an audit event.
- Hardened Shopify cart creation: strict ProductVariant GIDs, top-level GraphQL error
  handling, required cart IDs and HTTPS checkout URL validation.
- Added production fail-closed checks for partial Shopify configuration, malformed store
  domains and non-HTTPS pool-sensor endpoints.
- Updated README, production handoff, environment guidance, Mac Start Here screen and API
  identifiers for V5.12.0. The unchanged UI bundle remains `5.11.0-ui7` intentionally.

## Confirmed operating rules represented in the build

- Paul and Laura Smith handle complaints/questions through `bendigo@hvswimschool.com`.
- Lessons are $22.50 each, billed by term and due on enrolment.
- Two absence credits per swimmer per term; no make-up lessons and no mid-term refund,
  subject to Australian Consumer Law.
- A parent/guardian stays onsite except for Stroke Development.
- No photos without required class/swimmer clearance.
- Public enquiries are retained for six months. Staff records are retained to the end of
  the relevant financial year unless a legal, safeguarding or dispute hold applies.
- Confirmed entity: HVS BENDIGO PTY LTD, ABN 46 687 937 962.

## Verification — 31 August 2026

- Full Python API/security suite: **124 passed, 1 intentionally skipped**.
- Live read-only smoke suite: **52/52 checks passed**, including protected backend health.
- Static checker: **19 pages, 14 precached files and 8 scripts passed**.
- Live HTTP security baseline: **20/20 checks passed**.
- Python compilation, dependency consistency and Git whitespace checks passed.
- In-app browser reloaded Management → Billing against the hardened live server; the
  complete invoice workspace rendered successfully with the existing authenticated session.
- Live protected health result: integrity `ok`, zero foreign-key violations, zero billing
  total mismatches, WAL active and integration-token encryption `current`.
- Security language remains honest: this is a tested baseline, not an “unhackable” claim or
  a replacement for an independent penetration test on final hosting/configuration.

## External work before production

Follow `PRODUCTION_HANDOFF.md` and `SECURITY_AUDIT_V5.10.md`. Source code cannot complete
account-owned or regulated setup:

- Existing Xero OAuth app, verified Xero Contact IDs, accountant-approved lesson account
  code/tax/line-amount type and a reviewed draft/status/payment test in the intended
  organisation. Leave `XERO_SYNC_ENABLED=false` until sign-off. Credit notes and live payroll
  export remain unimplemented and hard-locked.
- Shopify Storefront/customer configuration, family-number metafields, approved products,
  variants, stock, checkout/refunds and authorised order/customer reconciliation.
- Managed PostgreSQL on Australian-region HTTPS hosting, private secrets, encrypted backups
  and restore drill, monitoring, management MFA, recovery/deletion/session controls,
  legal/privacy/WCAG review and an independent penetration test.
- Google and Apple family sign-in credentials and callback/domain verification.
- Email/SMS/Web Push providers, consent, quiet hours, receipts and opt-outs.
- Current AUSTSWIM/SWIM/Autism Swim evidence and issued artwork; never use scraped logos.
- Approved Printify, embroidery/manual and specialist swim suppliers plus passed physical
  samples and written artwork/brand rights.
- Commercial weather entitlement and an authenticated HTTPS pool sensor only if a venue
  supplies a reliable feed. Pool water temperature remains staff verified until then.

Do not commit `.env`, databases, generated `www/`, native `ios/`/`android/` folders or ZIPs.
