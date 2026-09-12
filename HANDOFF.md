# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Codex
**Last updated:** 2026-09-12 by Codex — sunlit website rebuild and isolated preview verified

The working directory was missing on arrival. Restored the exact private GitHub main
commit `676094ff874af6c2bd6fb5ff98fef979367773bc` into the empty local Developer path.
This restored source only; no previous private runtime database was present or recovered.

## Latest release — UI19 sunlit rebuild

Branch `codex/sunlit-rebuild`, based on newer UI18 branch commit `beab5cb`.
Read `SUNLIT_REBUILD.md` for changes, test evidence and precise launch blockers.

- Bright photographic homepage, program explorer, first-lesson guide and shared public/portal polish.
- Consistent private-price enquiry messaging, simpler general enquiries and family progress copy.
- New isolated `preview-local.command`: loopback port 8772; no `.env` or inherited provider credentials.
- Sole source copy moved to `/Users/andrewhains/Developer/HV-Swim-School` on Andrew’s instruction.
- Preview runtime data is `data/local-preview/`, Git-ignored and synthetic only.
- Final backend suite: 152 passed / 1 existing skip; five Node scripts and static checks passed.
- 156 responsive browser matrix checks; 53 smoke and 20 security baseline checks passed.
- No public deployment, real financial transaction, email or payroll transmission.

### Next up

Review the local design with Andrew. Confirm the business decisions and credentials in
`SUNLIT_REBUILD.md` before production work. Real photography and private tuition pricing
are particularly useful next inputs. Production database adaptation, outbound delivery
and provider acceptance remain separate engineering work. Do not enable live integrations
or deploy publicly without Andrew’s explicit approval.

## Previous release — UI18 (historical)


Presentation revision `5.13.0-ui18`; service-worker caches end in `-19`.
Working branch: `codex/platform-rebuild-20260906`, based on verified private main
`406306a0628cbd3ba8e36e724d4165465b9f2465`. Read `PLATFORM_REBUILD.md` and
`WORKFORCE_OPERATIONS.md` before deployment or continuing backend work.

- Preserved the approved logo, public content, enquiry-first enrolment, staff-only
  uniforms, Xero lesson boundary and Shopify merchandise boundary. Apps remain paused.
- Polished the shared navy/cyan/gold visual system and portal workspaces. Added optional
  lightweight WebGL water with reduced-motion, low-power and failure fallbacks.
- Rebuilt staff workday/working hours: exact server seconds, paid/unpaid breaks,
  durable retry references, automatic submission and restart-safe persisted state.
- Added assigned-manager review, rejection/resubmission, reasoned versioned corrections,
  reapproval, immutable approved CSV/XLSX batches and separately approved amendments.
- Full-ledger daily/weekly/fortnight/month/custom reports split overnight and daylight-
  saving intervals. Old manual daily/weekly entry remains, with overlap/export guards.
- Extended existing accounts with invitation/activation, generic recovery, private
  handover controls, encrypted TOTP, proof-attempt limits and session revocation.
- Added a tested per-employee Xero AU 2.0 draft-timesheet adapter with durable outcomes.
  **Live payroll stays locked:** provider resource import and operator reconciliation
  UI remain outstanding; no real payment, payroll or email was sent.
- Fixed preview caching and development-tool security advisories. Python and JavaScript
  dependency audits report no known vulnerabilities. One glob deprecation remains.
- Final checks: **151 Python passed, 1 existing seed-dependent test skipped**;
  two upstream Python test-client deprecation warnings remain. Static checker and all
  five Node regression suites passed; 53 smoke and 20/20 HTTP security checks passed.
- Browser checks covered public mobile/tablet/desktop, family and management route
  matrices, staff routes and start/break/finish/approve/export. Detailed limits and
  counts are in `PLATFORM_REBUILD.md`; these are not independent certification.
- Active isolated preview: `http://127.0.0.1:8769/index.html`, data directory
  `/tmp/hv-swim-rebuild.lZtm3g`. Its marked QA shift/export is synthetic. The old
  8768 preview may still run older loaded backend code; do not use it for UI18 testing.
- API-generated sample CSV/XLSX files in `/private/tmp/hv-swim-delivery-20260906`
  reconcile 43,254 seconds / 12.015 hours. They contain labelled fictional records.
- SQLite is the implemented database. Unsupported DATABASE_URL/HV_DATABASE_URL settings
  now fail closed. No real private database was restored, migrated or published.

## Previous presentation release — historical

Presentation revision `5.13.0-ui16`; service-worker caches end in `-17`.
Read `INTERACTIVE_3D_REBUILD.md` for this release's complete evidence.

- New shared `assets/experience.css` and `assets/experience.js` apply across all pages.
- Native CSS 3D pool/program explorer on home; rotatable colour-study bottle in the shop.
- Native touch scrolling, keyboard rotation/reset, OS reduced-motion handling, saved
  pause preference, offscreen/hidden-tab animation suspension and pointer card depth.
- Reworked public, shop, sign-in and portal typography, palettes, cards, spacing and navigation.
- Legacy style files use `@layer legacy`; do not undo this or specificity conflicts return.
- Public homepage no longer promotes staff uniforms.
- Shared date formatting now handles legacy clock timestamps; business dates use
  `formatToParts`. Staff daily hours correctly follow the selected Monday–Sunday week.
- New interaction/date regressions are wired into npm test and GitHub CI.
- Final checks: 128 Python passed/1 skipped, four Node regression scripts passed,
  49 public + 86 portal + 12 supporting-page browser checks passed, 53 smoke checks and
  20/20 HTTP security checks passed. Two existing Python deprecation warnings remain.
- Preview runtime data: `/tmp/hv-swim-3d-preview`, with development sample accounts only.
  A marked QA daily-hour draft exists there; no record was transmitted to Xero.
- Source restoration did not restore previous private runtime data or credentials.

## Earlier foundation

The existing V5.13 static site and FastAPI platform were upgraded in place. The public
experience, enquiry flow, family/staff/management portals, roster, incidents and swimmer
progress are materially more polished and safer. The app phase remains paused. Enrolment
is enquiry-only; Xero is the lesson-payment boundary and Shopify is the merchandise boundary.

The sole current working copy is `/Users/andrewhains/Developer/HV-Swim-School`, outside iCloud.
The 5 September handoff reported an earlier migration with private data checksums, but
that folder and private runtime data were absent on 6 September. This session restored
source from GitHub, not those earlier private records. Private runtime data remains Git-ignored.

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

## Earlier foundation verification — historical

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
