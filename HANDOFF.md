# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-29 by Codex

## Current state

V5.4 is the current premium production foundation. The public website, family/staff/
management workspaces, PWA, Capacitor mobile shell, merchandise studio and FastAPI service
have completed a full design, workflow, security, accessibility, responsive and production-
readiness pass. Outdated former-owner content remains removed from this repository.

The implementation stays honest about external boundaries: HV Swim already has Xero, while
the website's OAuth/readiness workflow is implemented but live payroll transmission remains
locked; Shopify/Printify/VistaPrint, commercial
weather, email, SMS, push, pool sensors, hosting and app stores still require HV Swim-owned
accounts, credentials and/or provider work. SQLite is preview-only and must be replaced
before real customer, child or payroll data is stored.

## Delivered in V5.4

- Privacy-first optional Facebook timeline, visitor consent gate, direct-page fallback,
  production CSP allowance and matching privacy disclosure.
- Source-linked SWIM Coaches & Teachers Australia, AUSTSWIM and Autism Swim directory
  records presented without implying instructor accreditation or misusing corporate logos.
- Venue-specific Acknowledgement of Country with an abstract HV-designed sun/water mark and
  a source link to the City of Greater Bendigo wording.
- Distinct locally optimised program, enquiry and teaching-approach campaign photographs;
  exact prompts, output paths and generic-image boundaries are in `IMAGE_ASSET_PROVENANCE.md`.
- Truthful pool fallback states: no sample number is shown as a current Wood Street reading.
- Required-choice program matcher, location-aware enquiry handoff and non-PII session draft
  recovery that never stores names, contact details or free-text notes.
- Role-specific family/staff action hubs and a management attention queue sourced from the
  existing API, plus accessible role-aware sign-in context without credential autofill.
- Locations now lead with venue details and venue-prefilled enquiries; the planned shop uses
  saved-list language until Shopify is genuinely active.
- Installed/native app smart launch checks the session and prioritises secure role access.
- Page-specific mobile quick actions wait until the opening hero has left view; favicon and
  PWA cache handling were refreshed for V5.4.

## Preserved from the V5.3 foundation

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
- PWA manifest, social metadata, service-worker cache, Capacitor handoff and release docs.
- `BRAND_GUIDE.md` records logo usage, palette, typography, asset roles and the physical-
  production boundary for merchandise.

## Verified 2026-08-29

- `pytest tests/ -q`: 69 passed, 1 intentionally skipped.
- Running-server smoke suite: public content/APIs, all three demo roles, protected data,
  management workflows and CSRF rejection passed.
- Production JavaScript dependency audit: no known vulnerabilities.
- Python dependencies pass `pip check`; the GitHub workflow runs the production Python 3.12
  audit with the five documented FastAPI/Starlette applicability exceptions in `SECURITY.md`.
- JavaScript syntax, Python tests, 19-page/44-cache-entry static
  check and mobile web-shell build passed.
- Real-browser desktop/mobile walkthrough covered the seven main public pages, Facebook
  consent fallback, new directory/Country sections, mobile navigation, matcher and enquiry,
  nine-product shop, native-launch paths and all three secure role dashboards/action flows.
  No console errors, horizontal overflow or broken loaded images were found.

## Next external work

Follow `PRODUCTION_HANDOFF.md`. Priorities are managed PostgreSQL and Australian hosting,
approved real-data migration, final term/class/location data, legal and WCAG review,
production MFA/recovery, completing Xero pay-period/idempotent payroll export work, physical
merchandise samples and supplier-approved artwork, Shopify activation, messaging providers,
native signing/accounts, backups/monitoring and an independent penetration test.

HV Swim must also nominate canonical address/phone/email details and correct the SWIM,
AUSTSWIM and Autism Swim directories. The external Autism Swim page still names Andrea.
Obtain current organisation-issued badge files/usage rights before replacing the neutral
directory-link cards. Confirm each venue's Country and review the acknowledgement wording.
Test the optional Facebook timeline on the final production domain, signed out and with common
privacy blockers, before treating the Meta embed as launch-ready.

The V5.3 PNG logo files remain suitable for digital use and physical samples. Before bulk print
or embroidery, commission a manually checked vector SVG/EPS/PDF, define CMYK/spot colours,
and approve a physical print/stitch sample. Do not treat an automatically traced or generated
file as final production artwork.

Do not commit `.env`, databases, generated native `ios/`/`android/` folders or delivery ZIPs.
