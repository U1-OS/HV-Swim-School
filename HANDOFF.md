# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-28 by Codex

## Current state

V5.2 is the current production foundation. The public site, family/staff/management
workspaces, PWA, Capacitor mobile shell, merchandise studio and FastAPI service have
received a full design, workflow, security, accessibility, responsive and production-
readiness pass. Andrea remains removed from current business content.

The implementation is honest about external boundaries: Xero is readiness/dry-run only;
Shopify/Printify/VistaPrint, commercial weather, email, SMS, push, pool sensors, hosting
and app stores still require HV Swim-owned accounts, credentials and/or provider work.
SQLite is preview-only and must be replaced before real customer, child or payroll data.

## Delivered in V5.2

- Premium responsive public experience, stronger navigation/CTAs, refined cards, spacing,
  interactions, reduced-motion support, forms and mobile layouts.
- Dedicated locations and conditions experience with map/directions links, venue status,
  staff-verified water readings, parking/accessibility, weather, lesson placeholders and
  location-specific enquiry actions.
- Accessible enquiry wizard, program finder, merchandise filters/dialog/cart and honest
  empty/error/offline states.
- Polished role workspaces with family bookings/swimmers/notices, staff roster/clocking/
  checklist/temperature/timesheets, and management operations/reporting/content controls.
- Management account/swimmer provisioning, mandatory first-login password replacement,
  account suspend/reactivate and temporary-password reissue workflows.
- Xero staff/calendar mapping and audited readiness preview. Outbound payroll transmission
  is deliberately locked until pay-period and idempotency controls are implemented.
- Server-cached Open-Meteo weather boundary with commercial production key requirement;
  water temperature is never inferred from outdoor weather.
- Shopify catalogue variant/product-type support and explicit Printify/manual/specialist
  supplier paths without fabricated checkout or fulfilment.
- Explicit static-file allowlist, production config guards, trusted hosts, HTTPS/session
  hardening, PBKDF2 passwords, encrypted Xero tokens, API content/path guards, audit logs,
  database race/index/migration protections and environment-safe demo accounts.
- GitHub Actions quality workflow, frozen pnpm lock, pinned Python dependencies, expanded
  static QA, SEO metadata, structured public pages and service-worker cache fixes.

## Verified 2026-08-28

- `pytest tests/ -q`: 68 passed, 1 intentionally skipped.
- Python dependency audit: no known vulnerabilities after 7 findings covered by the five
  documented FastAPI/Starlette compatibility exceptions in `SECURITY.md`.
- Production JavaScript dependency audit: no known vulnerabilities.
- JavaScript syntax, Python compilation, 19-page/36-cache-entry static check and mobile
  web-shell build: passed.
- Real-browser desktop/tablet/mobile walkthrough completed across all major public pages,
  enquiry submission, shop/cart, family, staff and management flows; no horizontal overflow
  or broken images found in the checked views.

## Next external work

Follow `PRODUCTION_HANDOFF.md`. Priorities are managed PostgreSQL and Australian hosting,
real-data migration, approved term/class/location data, legal and WCAG review, production
MFA/recovery, Xero OAuth/pay-period implementation, Shopify catalogue and physical product
sampling, provider adapters/consent, app-store signing/accounts, backups/monitoring and an
independent penetration test.

Do not commit `.env`, databases, generated native `ios/`/`android/` folders or delivery ZIPs.
