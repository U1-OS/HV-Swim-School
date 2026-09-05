# Premium V2 upgrade review — 5 September 2026

## Scope and approach

Continued the existing static HTML/CSS/JavaScript + FastAPI/SQLite codebase. Retained
the previous agent's uncommitted visual work and the enquiry-only enrolment changes;
no framework replacement or new production JavaScript dependencies. Reviewed public
pages, shared UI, portal routes, database migrations, authentication and the existing
Xero/Shopify integration boundaries. No live customer, provider or production data was
used for testing.

## Implemented and corrected

- Preserved the navy/aqua/gold brand, local font and image assets, responsive cards,
  improved homepage/program/location layouts, fee calculator and lesson matcher.
- Replaced unsourced named testimonials with honest learning themes. Added an explicit
  development-preview notice so seeded class/account data is not presented as live.
- Fixed the community-card layout overflowing at 320 px; improved focus contrast,
  mobile form sizing, calculator layout and reduced-motion counter behaviour. Removed
  continuous motion from the lesson match result. Shared asset caches are versioned ui9.
- Enquiry categories cover lessons, existing families, lesson questions, private lessons,
  billing, merchandise, feedback and general enquiries. Non-lesson enquiries go straight
  to contact/message details instead of requiring a child's profile. Trimmed/validated
  inputs, callback phone checks and readable API validation errors are shared with the
  existing form flow. Public enquiry throttling and insertion are now atomic.
- Fee estimates are not bookings or payment demands. Private pricing is confirmed by
  staff, example term lengths are labelled, and possible absence credits are not deducted
  automatically. URL-supplied totals are not trusted. Self-enrolment remains disabled.
- Staff/admin can record reviewed swimming skills, status, instructor feedback and a
  next step. Families see only their own swimmers' latest updates and existing awards.
  Observations are append-only; narrative fields are encrypted. Progress meters count
  reviewed skills and explicitly do not claim curriculum/level completion.
- Management can edit future published roster shifts through the existing builder.
  Overlapping shifts for the same worker are rejected across venues. Past roster records
  remain preserved; corrections to actual hours belong in reviewed timesheets.
- Incident reporting now includes labelled severity, first aider, emergency-services
  attendance, staff-only supporting notes and an encrypted management review. A review
  is required to close a report. Family responses omit private review/supporting fields.
- Stale pool readings and missing weather no longer appear as current measurements or
  an invented feels-like zero temperature in the family dashboard.
- FastAPI 0.141.1, Starlette 1.6.0 and pytest 9.1.1 were installed and tested together.
  Removed the old dependency-advisory exceptions from CI. The Mac launcher now selects
  Python 3.12+ and preserves the previous virtual environment.
- Added `scripts/browser-qa.mjs` for repeatable public/role page layout checks. It uses
  the existing browser tool externally and does not add a website dependency.

## Verification

- Full isolated Python suite: 128 passed, 1 intentionally skipped. Two upstream
  TestClient/httpx/AnyIO deprecation warnings remain; no new runtime library added just
  to suppress them.
- Dependency audit of the updated QA environment: no known vulnerabilities reported.
  This is an advisory check, not a claim of being unhackable or independently penetration tested.
- Static consistency: 19 pages, 14 precached files, 8 scripts passed. All JavaScript
  syntax, Mac launcher shell syntax and Git whitespace checks passed.
- Public responsive browser matrix: 49 checks at 320, 375, 390, 430, 768, 1024 and 1440 px;
  no detected horizontal overflow, missing visible images or browser errors.
- Management responsive matrix covers 21 routes at 320 and 1024 px. Family and staff
  matrices cover 11 routes each at both widths.
- Sign-in and sign-out regressions exercise delayed optional-provider configuration,
  handled logout failure and server-confirmed redirect behaviour.
- HTTP smoke/security results and the remaining role checks are recorded in `HANDOFF.md`.

## Deliberate production boundaries and remaining work

- SQLite remains a development/preview store. An approved production database, encrypted
  backups and restore drill, HTTPS hosting, secret management, monitoring and deployment
  review are still required. No customer database is uploaded to GitHub.
- Existing Xero OAuth/configuration and accountant-approved account/tax settings are
  required. DRAFT invoice handoff stays gated. Live payroll export and credit-note
  automation are not implemented. The website never marks a payment paid speculatively.
- Shopify requires an approved real catalogue, variants, inventory, customer mappings and
  checkout/refund testing. Printify/VistaPrint/specialist suppliers need approved samples,
  artwork rights and account configuration. Staff uniforms remain role-protected.
- Google/Apple identity needs business-owned credentials and callback/domain setup.
  Email/SMS and off-device push need provider delivery/consent/retry work; current website
  alerts are not guaranteed instant delivery when the browser is closed.
- Qualification logos require current evidence and authorised artwork. No fabricated
  affiliations, accreditation, testimonials or completed orders were added.
- Staff-confirmed pool readings are not a live sensor feed. Weather needs the appropriate
  commercial entitlement before production.
- The school must approve its real curriculum/skill list, swimmer records, classes,
  capacity, term dates and roster. There is no fabricated curriculum, automatic level
  promotion, or roster draft/publish approval process in this pass.
- Complete real-device VoiceOver/keyboard and assistive-technology review, production
  performance measurements, legal/privacy/retention review and an independent security
  assessment before using the platform for children's records. App delivery remains paused.

## Storage and collaboration

The current working directory is `/Users/u1/Developer/HV-Swim-School`, outside iCloud
Desktop/Documents. `AGENTS.md` instructs future sessions to use this directory and push
verified updates to the private GitHub repository. Private runtime data and credentials
stay excluded. A GitHub source backup is not a backup of the live business database.
