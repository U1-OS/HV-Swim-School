# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-31 by Codex — V5.10.1 professional refinement complete

## Current state

V5.10.1 is the verified production foundation for the premium public website and secure
family, staff and management platform. The native-app phase remains paused and both app
source routes return 404; current work should stay focused on the website and browser
platform.

The release preserves the real HV Swim business rules, Laura-led identity, Wood Street and
Bendigo East content, live Bendigo weather, staff-verified water readings, Xero-only lesson
payment route and Shopify-only merchandise route. It does not fabricate payments, stock,
provider connections, pool sensors, accreditation or background push delivery.

## Delivered through V5.10.1

- Preserved the V5.10.0 premium visual system, responsive public journey and protected
  family/staff/management workflows without rebuilding or removing working functionality.
- Added an accessible **Find a section** search to every role-specific workspace. It filters
  grouped navigation, reports an empty result, participates in the mobile focus trap and
  supports Escape-to-clear without closing the drawer.
- Improved the 24-product public merchandise experience with progressive rendering: six
  products initially on mobile and nine on wider screens, followed by keyboard-friendly
  **Show more products** loading. Filtering, searching and sorting reset the result window.
- Removed stale “saved collection” and preview-cart language. Planned products and kits are
  explicitly non-orderable; cart, stock and checkout remain hidden until approved products
  are connected to the live Shopify catalogue. Staff uniforms remain role-protected.
- Disabled browser geolocation in the Permissions Policy because staff time records use a
  selected workplace and timestamps, not GPS. Camera and microphone remain disabled too.
- Fixed the management class-availability singular/plural copy and refreshed the entire
  website/PWA asset cache line to V5.10.1 / `5.10.1-ui6`.
- Retained permanent family (`HVS-…`), student (`HVS-S-…`) and worker (`HVS-W-…`) numbers;
  automatic lesson-purchase assignment; encrypted child safety profiles; staff clock/break
  records; incident reports; lesson registers; achievements; eight certificate styles;
  qualification uploads and expiry reminders; tickets; rosters; alerts and pool conditions.

## Confirmed operating rules represented in the build

- Paul and Laura Smith handle complaints/questions through `bendigo@hvswimschool.com`.
- Lessons are $22.50 each, billed by term and due on enrolment.
- Two absence credits per swimmer per term; no make-up lessons and no mid-term refund,
  subject to Australian Consumer Law.
- A parent/guardian stays onsite except for Stroke Development.
- No photos without the required class/swimmer clearance.
- Public enquiries are retained for six months. Staff records are retained to the end of
  the relevant financial year unless a legal, safeguarding or dispute hold applies.
- Confirmed entity details are HVS BENDIGO PTY LTD, ABN 46 687 937 962. Business/postal
  details remain in `PRODUCTION_HANDOFF.md` for final verification.

## Verification — 31 August 2026

- Full Python API/security suite: **114 passed, 1 intentionally skipped**.
- Running-server read-only smoke suite: **49/49 checks passed**.
- Static checker: **19 pages, 14 precached files and 8 scripts passed**.
- Live HTTP security baseline: **20/20 checks passed**.
- JavaScript syntax, Python compilation and Git whitespace checks passed.
- In-app browser QA at 390×844 verified six-to-twelve progressive shop loading, keyboard
  focus transfer, all 20 management routes, grouped navigation search/reset and zero
  horizontal overflow. Browser diagnostics contained zero console errors or warnings.
- Security limits remain honest: these checks are a baseline, not an “unhackable” claim or
  a replacement for a penetration test against final production hosting/configuration.

## External work before production

Follow `PRODUCTION_HANDOFF.md` and `SECURITY_AUDIT_V5.10.md`. Source code alone cannot make
the following services live:

- Managed PostgreSQL on Australian-region HTTPS hosting, private secrets, encrypted
  backups/restore drill, monitoring, management MFA, recovery/deletion/session controls,
  legal/privacy/WCAG review and an independent penetration test.
- Existing Xero OAuth app, family/student reference mapping, invoice/payment/credit
  reconciliation, payroll mappings, real pay periods and idempotent exports.
- Shopify Storefront/customer configuration, family-number metafields, approved products,
  variants, stock, checkout/refunds and tested staff-uniform access boundaries.
- Approved Printify, VistaPrint/manual embroidery and specialist swim suppliers, written
  blank-brand/artwork rights and passed physical samples for every product family.
- Google and Apple family sign-in credentials and production callback/domain verification.
- Email/SMS/Web Push providers, consent, quiet hours, receipts and opt-outs.
- Current AUSTSWIM/SWIM/Autism Swim evidence and issued artwork. Never substitute scraped or
  generic organisation logos. Current external directories still need Andrea removed.
- Commercial weather entitlement for production and a pool sensor only if a venue provides
  a reliable authenticated feed. Until then, water temperature remains staff verified.

Do not commit `.env`, databases, generated `www/`, native `ios/`/`android/` folders or delivery ZIPs.
