# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Codex
**Last updated:** 2026-09-05 by Codex — Premium V2 whole-project upgrade and local-storage migration

## Current state

The existing V5.13 static site and FastAPI platform were upgraded in place. The public
experience, enquiry flow, family/staff/management portals, roster, incidents and swimmer
progress are materially more polished and safer. The app phase remains paused. Enrolment
is enquiry-only; Xero is the lesson-payment boundary and Shopify is the merchandise boundary.

The sole working copy is now `/Users/u1/Developer/HV-Swim-School`, outside iCloud.
The old `~/Documents/GitHub/HV-Swim-School` path no longer exists. The move preserved
8,151 files, produced zero dataless placeholders and retained matching source and private
database checksums. Private runtime data remains Git-ignored.

## Delivered

- Premium responsive visual pass retained and refined across public pages and portals.
- Development-preview data is labelled; fabricated named testimonials were removed.
- 320 px overflow, mobile form sizing, focus contrast and reduced-motion behaviour fixed.
- Lesson matcher and fee estimates have enquiry/payment boundaries and do not invent private pricing.
- One form routes lessons, billing, merchandise, feedback and existing-family questions;
  non-lesson messages do not request a swimmer profile or learning preferences.
- Append-only, encrypted swimmer skill observations with current family-visible feedback.
- Future-roster editing with overlap and past-record protections.
- Incident severity, first aider, emergency attendance, encrypted internal notes and
  mandatory management review before closure.
- Stale pool and unavailable weather readings no longer appear as current values.
- Sign-in handlers are bound before optional provider lookup; native fallback cannot send
  credentials in a GET URL. Sign-out redirects only after server-confirmed logout.
- FastAPI 0.141.1, Starlette 1.6.0 and pytest 9.1.1; CI advisory exceptions removed.
- Python 3.12 local environment prepared as `.venv312`; old `.venv` preserved.
- Repeatable role/page browser matrix and UI auth regressions added.

## Verification

Final evidence is in `PREMIUM_V2_UPGRADE_REPORT.md`. The core results are:

- Python tests: **128 passed, 1 intentionally skipped**.
- Static checker: **19 pages, 14 precached files and 8 scripts passed**.
- Live read-only smoke suite: **53 checks passed**.
- Live HTTP security baseline: **20/20 checks passed**.
- Public responsive matrix: **49 checks**, 320–1440 px.
- Family and staff matrices: **22 checks each**, 320 and 1024 px.
- Dependency audit: **no known vulnerabilities found**.

## Still requires owners, credentials or professional review

- Managed production database, HTTPS hosting, secret management, encrypted backup/restore
  drill, monitoring, management MFA and independent penetration/accessibility/legal review.
- Existing Xero organisation OAuth, approved contacts/accounts/tax settings and real DRAFT
  invoice reconciliation. Live payroll export and credit-note automation remain locked.
- Approved Shopify catalogue, stock/variants/checkout/refunds and customer metafields.
  Printify/VistaPrint/specialist suppliers still need accounts, rights and physical samples.
- Google/Apple credentials; email/SMS/off-device push delivery; commercial weather terms;
  current association evidence/artwork; authenticated pool sensor if a venue supplies one.
- Staff-approved real curriculum, class capacity, term, roster and swimmer records.

Do not commit `.env`, databases, certificates, customer records, `.venv*`, generated `www/`,
native mobile folders or ZIPs. Push every verified source update to the private GitHub repo.
