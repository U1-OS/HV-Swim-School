# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-28 by Codex

## Current state

V5.3 is the current premium production foundation. The public website, family/staff/
management workspaces, PWA, Capacitor mobile shell, merchandise studio and FastAPI service
have completed a full design, workflow, security, accessibility, responsive and production-
readiness pass. Outdated former-owner content remains removed.

The implementation stays honest about external boundaries: Xero is connected/readiness
capable but payroll transmission remains locked; Shopify/Printify/VistaPrint, commercial
weather, email, SMS, push, pool sensors, hosting and app stores still require HV Swim-owned
accounts, credentials and/or provider work. SQLite is preview-only and must be replaced
before real customer, child or payroll data is stored.

## Delivered in V5.3

- Premium public visual system with refined typography, spacing, navigation, hero, cards,
  forms, responsive layouts, calm water-inspired depth and restrained interaction motion.
- Premium role-aware family, pool-deck and management workspaces with redesigned sign-in,
  topbar, sidebar, mobile tabbar, dashboards, tables, forms, status and empty/error states.
- Refined transparent HV Swim full logo and simplified digital mark, monochrome proofs,
  refreshed Open Graph artwork and a complete opaque/mask-safe app-icon family.
- Locally hosted Manrope variable typography and a local SVG interface icon set so Mac,
  Windows, iOS and Android render the same visual language without emoji-dependent icons.
- Dedicated locations and conditions experience with maps, venue status, parking,
  accessibility, current weather, lesson placeholders, staff-verified water readings and
  location-specific enquiry actions.
- Guided lesson finder and program pathway, persistent merchandise collection, nine-product
  supplier/sample workflow, and explicit Shopify/Printify/VistaPrint/specialist boundaries.
- Family bookings/swimmers/notices, staff roster/clock/location/pool checks/timesheets, and
  management enrolments/accounts/site content/locations/reporting/merch/Xero readiness.
- Responsive, focus, menu, overflow, reduced-motion, contrast, semantic and accessible-name
  fixes across public and secure screens.
- V5.3 PWA manifest, social metadata, service-worker cache, Capacitor handoff and release docs.
- `BRAND_GUIDE.md` records logo usage, palette, typography, asset roles and the physical-
  production boundary for merchandise.

## Verified 2026-08-28

- `pytest tests/ -q`: 68 passed, 1 intentionally skipped.
- Running-server smoke suite: public content/APIs, all three demo roles, protected data,
  management workflows and CSRF rejection passed.
- Python dependency audit: no known vulnerabilities after the five documented, reviewed
  FastAPI/Starlette compatibility exceptions in `SECURITY.md`.
- Production JavaScript dependency audit: no known vulnerabilities.
- JavaScript syntax, Python compilation, XML/icon dimensions, 19-page/41-cache-entry static
  check and mobile web-shell build passed.
- Real-browser desktop/tablet/mobile walkthrough covered all major public pages, mobile menu,
  enquiry steps, nine-product shop/cart, family, staff clock/pool checks, and management
  enrolments/timesheets/website/locations/merchandise/Xero views. No horizontal overflow or
  broken loaded images were found in the checked views.

## Next external work

Follow `PRODUCTION_HANDOFF.md`. Priorities are managed PostgreSQL and Australian hosting,
approved real-data migration, final term/class/location data, legal and WCAG review,
production MFA/recovery, completing Xero pay-period/idempotent payroll export work, physical
merchandise samples and supplier-approved artwork, Shopify activation, messaging providers,
native signing/accounts, backups/monitoring and an independent penetration test.

The V5.3 PNG logo files are suitable for digital use and physical samples. Before bulk print
or embroidery, commission a manually checked vector SVG/EPS/PDF, define CMYK/spot colours,
and approve a physical print/stitch sample. Do not treat an automatically traced or generated
file as final production artwork.

Do not commit `.env`, databases, generated native `ios/`/`android/` folders or delivery ZIPs.
