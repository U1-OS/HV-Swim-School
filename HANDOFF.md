# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-29 by Codex — V5.5 complete and ready to push

## Current state

V5.5 is the current premium production foundation. The public website, family/staff/
management workspaces, installable PWA, Capacitor mobile shell, 21-product merchandise
studio and FastAPI service have completed a design, workflow, security, accessibility,
responsive and production-readiness pass. Former-owner content remains removed.

The repository is intentionally honest about external boundaries. The app is a working PWA
and Capacitor-ready foundation, not a signed App Store or Google Play release. Public alerts
reach open website/app pages and family in-app notices; background Web Push/APNs/FCM, email
and SMS are not simulated. Water temperature is staff-verified until a compatible sensor
feed is selected. Xero readiness is present, but live payroll transmission remains locked.
SQLite and demo accounts are preview-only and must not hold real customer, child or payroll
data.

## Delivered in V5.5

- A premium 21-product catalogue covering kids' swimwear, rashies, shorts, hooded and regular
  towels, cap, goggles, training mitts, bag, bottle, adult insulated cup, child warm-drink cup,
  sun hat and a complete staff uniform capsule.
- Product audience, production method, supplier route, fulfilment state, sample gate,
  Printify mapping and Shopify publication controls; VistaPrint remains a truthful manual/
  bulk route and unapproved premium brands are never presented as partners.
- New premium children and staff merchandise campaign concept images. Exact built-in image-
  generation prompts, masters and web outputs are in `IMAGE_ASSET_PROVENANCE.md`.
- Asynchronous support messaging from every public page and the family app into the secure
  Staff/Management Tickets queue, with reference numbers, thread replies, ownership,
  priority, status, private notes, rate limiting, honeypot protection and audit records.
- Management public-alert publishing plus automatic pool closure/change/reopening notices.
  Active pages poll the public feed; family accounts receive in-app notices.
- Eight swimmer achievement templates with family-visible evidence, staff-private notes,
  audited issue/revocation and eight printable certificate styles. Certificates are
  recognition items, not qualifications or accreditation.
- Refined app, shop, role dashboards, mobile copy, service-worker cache and V5.5 metadata.
- Source-linked association records and an issued-badge requirements guide. No corporate
  badge is scraped, redrawn or shown until HV Swim supplies the current authorised file and
  confirms usage rights.
- Updated brand, privacy, terms, mobile, production and merchandise documentation.

## Preserved from the V5.4/V5.3 foundation

- Premium public design system, responsive navigation, local Manrope typography, accessible
  controls, calm water-inspired depth and restrained animation.
- Refined HV Swim logo/mark, social artwork and mask-safe app icon family.
- Programs, guided enquiry, teaching approach, optional Facebook timeline, local SEO,
  Acknowledgement of Country and venue-specific Locations & Pool Conditions experience.
- Live Bendigo outdoor weather with a truthful fallback, venue maps, parking/accessibility,
  today's-lesson placeholders and staff-verified pool readings.
- Family bookings/swimmers/notices; staff roster/clock/location/timesheets/pool checks; and
  management enrolments/accounts/content/locations/reporting/merch/Xero readiness.
- Installable PWA, offline shell, iOS/Android Capacitor handoff and release-gate documents.

## Verified 2026-08-29

- Full Python suite: **87 passed, 1 intentionally skipped**.
- Running-server smoke suite: **37 checks passed**, including V5.5 health, 21 products,
  support tickets, alerts and achievements.
- Static site checker: **19 pages, 50 service-worker cache entries and 8 scripts passed**.
- JavaScript syntax and `git diff --check`: passed.
- Capacitor web shell: built successfully for the approved localhost simulator origin;
  production build correctly requires a real HTTPS app origin.
- Real-browser desktop/mobile walkthrough covered public pages and the new public-message,
  family-message, staff-ticket, achievement and management-alert flows. No horizontal
  overflow, broken loaded images or application console errors were found. A final repeat
  was unavailable only because the in-app browser's admin security-policy check temporarily
  refused localhost; no security control was bypassed.

## External work before production

Follow `PRODUCTION_HANDOFF.md`. Priorities are managed PostgreSQL and Australian hosting,
approved real-data migration, final business/contact/term/class data, production auth/MFA/
recovery, legal and WCAG review, backups/monitoring and an independent penetration test.

HV Swim must provide and configure:

- Shopify and Printify accounts/credentials, supplier mapping, fulfilment policy, product
  pricing, approved samples and returns/shipping settings; VistaPrint is a manual quote and
  bulk-order workflow unless it supplies a supported integration.
- Xero organisation OAuth plus approved pay-period and idempotent payroll export rules.
- Email/SMS and Web Push/APNs/FCM providers, consent, token retention and opt-out behaviour.
- The final HTTPS domain, Apple/Google developer accounts, signing, store declarations,
  screenshots and device beta testing.
- A commercial weather key if required and a compatible pool sensor only if automatic water
  temperatures are wanted; otherwise staff continue publishing verified daily readings.
- Current issued association badge files and written usage rights. Correct the external
  Autism Swim listing that still names Andrea, and confirm all directory details.
- A manually checked vector SVG/EPS/PDF logo, CMYK/spot colours and physical print/stitch
  samples before bulk merchandise or embroidery.

Do not commit `.env`, databases, generated native `ios/`/`android/` folders or delivery ZIPs.
