# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-30 by Codex — V5.10.0 professional website/platform upgrade complete

## Current state

V5.10.0 is the verified production foundation for the premium public website and secure
family, staff and management platform. The native-app phase is paused and both app source
routes return 404; current work should stay focused on the website and browser platform.

The release keeps the real HV Swim business rules, Laura-led identity, Wood Street and
Bendigo East location content, live Bendigo weather, staff-verified pool water readings,
Xero-only lesson payment route and Shopify-only merchandise route. It does not fabricate
payments, stock, provider connections, pool sensor readings, accreditation or push delivery.

## Delivered in V5.10.0

- Reworked public and platform styling into a consistent premium system with stronger
  typography, spacing, card depth, page hierarchy, restrained animation, responsive menus,
  mobile bottom navigation, clearer calls to action and reduced visual clutter.
- Cleaned family, staff and management navigation into role-specific groups and added
  next-action/attention views without removing existing working routes.
- Added permanent family (`HVS-…`), student (`HVS-S-…`) and worker (`HVS-W-…`) numbers.
  Account/swimmer creation assigns them, and lesson purchase transactionally rechecks and
  backfills both family/student numbers before snapshotting them into the Xero-bound charge.
- Added staff clock-on, start/end break and clock-off, plus retained manual weekly/daily
  hour entry for corrections or completed weeks. Records use timestamps and a selected
  workplace only; the browser and API do not collect GPS or continuous device location.
- Added worker-number mapping fields for the existing Xero payroll employee/calendar and a
  separate Shopify customer GID used only for private staff-uniform orders. Xero payroll
  transmission remains locked behind the documented production implementation work.
- Added a private staff incident/injury workflow linked to family, student and worker
  numbers. Objective account, observed injury/symptoms, first aid, follow-up and witnesses
  are encrypted at rest; audit entries exclude the narrative. Families see only their own
  reports and management can track follow-up status.
- Preserved encrypted child emergency/allergy/medication/support profiles, family absence
  rules, lesson registers, achievements, eight progress-certificate styles, qualification
  document uploads/expiry reminders, rosters, tickets and pool-condition workflows.
- Tightened the 24-product premium merchandise plan. Planned products and kits are visibly
  non-orderable; saved-cart simulation is removed and cart/checkout stay hidden until an
  approved live Shopify catalogue is connected. Staff merchandise remains role-protected.
- Clarified production boundaries throughout README, privacy, terms, security and handoff
  documentation. Added `SECURITY_AUDIT_V5.10.md` and a repeatable live HTTP audit script.
- Paused mobile metadata and removed app routes from public serving, sitemap and launch scope.
- Updated the full site and PWA cache line to V5.10.0 / `5.10.0-ui4`.

## Confirmed operating rules represented in the build

- Paul and Laura Smith handle complaints/questions through `bendigo@hvswimschool.com`.
- Lessons are $22.50 each, billed by term and due on enrolment.
- Two absence credits per swimmer per term; no make-up lessons and no mid-term refund,
  subject to Australian Consumer Law.
- A parent/guardian stays onsite except for Stroke Development.
- No photos without the required class/swimmer clearance.
- Public enquiries are retained for six months. Staff records are retained to the end of
  the relevant financial year unless a legal, safeguarding or dispute hold applies.
- Confirmed entity details are recorded as HVS BENDIGO PTY LTD, ABN 46 687 937 962, with
  business/postal details listed in `PRODUCTION_HANDOFF.md` for final verification.

## Verification — 30 August 2026

- Full Python API/security suite: **114 passed, 1 intentionally skipped**.
- Static site checker: **19 pages, 14 precached files and 8 scripts passed**.
- Live HTTP security baseline: **20/20 checks passed**.
- JavaScript syntax, Python compilation and Git whitespace checks passed.
- Real headless Chrome QA covered the 390×844 management incident workflow, planned shop
  and 1440px homepage. All had zero horizontal overflow and zero console/page errors.
- Mobile incident heading focus outline is suppressed for programmatic route focus, Wood
  Street is the default report location, and the public kit controls remain disabled with
  `Shopify setup required` until the live source is approved.
- Security limits are stated honestly: these checks are a baseline, not an “unhackable”
  claim or a substitute for a penetration test against final hosting/configuration.

## External work before production

Follow `PRODUCTION_HANDOFF.md` and `SECURITY_AUDIT_V5.10.md`. Source code alone cannot make
the following services live:

- Managed PostgreSQL on Australian-region HTTPS hosting, private secret storage, encrypted
  backups/restore drill, monitoring, management MFA, recovery/deletion/session controls,
  legal/privacy/WCAG review and an independent penetration test.
- Existing Xero OAuth app, family-number/contact mapping, student-number invoice reference,
  invoice/payment/credit reconciliation, payroll mappings, pay periods and idempotent exports.
- Shopify Storefront/customer configuration, family-number customer metafield, approved
  products/variants/stock/checkout/refunds and tested staff-uniform access boundaries.
- Approved Printify, VistaPrint/manual embroidery and specialist swim suppliers, written
  blank-brand/artwork rights and passed physical samples for every product family.
- Google and Apple family sign-in credentials and production callback/domain verification.
- Email/SMS/Web Push providers, consent, quiet hours, delivery receipts and opt-outs.
- Current AUSTSWIM/SWIM/Autism Swim evidence and issued artwork. Never substitute scraped
  or generic organisation logos. Current external directories still need Andrea removed.
- Commercial weather entitlement for production and a pool sensor only if a venue provides
  a reliable authenticated feed. Until then, water temperature remains staff verified.

Do not commit `.env`, databases, generated `www/`, native `ios/`/`android/` folders or delivery ZIPs.
