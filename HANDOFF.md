# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-31 by Codex — V5.11.0 finance and portal upgrade complete

## Current state

V5.11.0 is the verified website and browser-platform release for HV Swim Bendigo. It
preserves the premium public website, real HV business rules, Laura-led identity, family,
staff and management workflows, Wood Street/Bendigo East locations, outdoor Bendigo
weather, staff-verified pool readings, Shopify-only merchandise route and Xero-only lesson
payment route. The native-app phase remains paused and its public routes stay blocked.

The major new capability is an accountable lesson-invoice ledger. It creates local drafts
from real pending lesson charges, requires management approval and can create only a Xero
**DRAFT** invoice after every connection/configuration gate passes. It does not fabricate a
Xero invoice, payment, credit note, refund, contact, tax treatment or Shopify order.

## Delivered in V5.11.0

- Added `billing_invoices`, immutable invoice lines and invoice-event history. A unique
  lesson-charge constraint prevents one charge being placed on two invoices.
- Added the Management → Billing & invoices workspace: unbilled charges grouped by family
  and term, local draft creation, review/approval, Xero readiness, Xero draft creation,
  status/payment refresh, manual-review warnings and a visible Shopify separation.
- Added the Family → Billing & invoices workspace. Families see only management-approved
  invoices and Xero-confirmed payment status; local drafts, internal notes, sync errors and
  idempotency keys are excluded.
- Added Xero Accounting API invoice support with tenant headers, stable idempotency keys,
  reviewed account/tax/line-amount settings, DRAFT-only creation and payment/status
  reconciliation. Rotated OAuth refresh tokens are persisted before the accounting call.
- Added production fail-closed validation: `XERO_SYNC_ENABLED=true` cannot start without
  complete Xero OAuth plus lesson account code, tax type and valid line-amount type.
- Kept payroll transmission separately hard-locked. Existing approved-hours readiness is
  still a read-only preview until real AU Payroll periods and duplicate-export tracking exist.
- Upgraded People & accounts with family number, student identities, active bookings,
  invoice count, outstanding/unbilled amounts, Xero Contact ID and Shopify Customer GID in
  one protected management view.
- Added lesson-billing work to the management command-centre attention queue and reorganised
  the sidebar into clearer Finance & sales and Website & communications groups.
- Encrypted private invoice management notes at rest. No card data is stored by the portal.
- Refined responsive billing cards, readiness panels, timelines, mobile controls and visual
  hierarchy across management and family portals. No horizontal overflow was found at
  390×844 or 1120px desktop.
- Updated API/static release identifiers, asset cache keys and service-worker caches to
  V5.11.0 / `5.11.0-ui7`.
- Updated README, production handoff, environment template and automated smoke coverage for
  the reviewed Xero invoice workflow.

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

- Full Python API/security suite: **117 passed, 1 intentionally skipped**.
- Live read-only smoke suite: **51/51 checks passed**, including family/admin billing.
- Static checker: **19 pages, 14 precached files and 8 scripts passed**.
- Live HTTP security baseline: **20/20 checks passed**.
- JavaScript syntax, Python compilation and Git whitespace checks passed.
- In-app browser QA covered Management Billing, People & accounts and Family Billing on
  desktop and 390×844 mobile. Zero horizontal overflow and zero console errors were found.
- Security language remains honest: this is a tested baseline, not an “unhackable” claim or
  a replacement for an independent penetration test on final hosting/configuration.

## External work before production

Follow `PRODUCTION_HANDOFF.md` and `SECURITY_AUDIT_V5.10.md`. Source code cannot complete
account-owned or regulated setup:

- Existing Xero OAuth app, verified Xero Contact IDs for each family, accountant-approved
  lesson account code/tax/line-amount type and an end-to-end draft/status/payment test in the
  intended organisation. Leave `XERO_SYNC_ENABLED=false` until that review is signed off.
- Xero credit-note handling remains unimplemented; absence eligibility never changes an
  invoice automatically. Payroll still needs real pay periods and idempotent exports.
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
- Commercial weather entitlement and an authenticated pool sensor only if a venue supplies
  a reliable feed. Pool water temperature remains staff verified until then.

Do not commit `.env`, databases, generated `www/`, native `ios/`/`android/` folders or ZIPs.
