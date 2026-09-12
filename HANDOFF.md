# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Root Codex — sole editor; requirements_audit backend handback complete
**Last updated:** 2026-09-13 by Codex — fresh rebuild explicitly authorised; branch codex/fresh-brand-rebuild

The working directory was missing on arrival. Restored the exact private GitHub main
commit `676094ff874af6c2bd6fb5ff98fef979367773bc` into the empty local Developer path.
This restored source only; no previous private runtime database was present or recovered.

## Current direction — FRESH REBUILD authorised

Andrew explicitly said: “take this as a new rebuild, remove all unwanted old items,
base it off today fresh build.” This supersedes further incremental theme patches.
The UI25 checkpoint is safely pushed as `1f714c2` on `codex/sunlit-rebuild`.
Active work is now `codex/fresh-brand-rebuild` in the SAME sole working copy.

Read `FRESH_REBUILD.md`. Replace the public frontend with one clean design system,
retain the verified backend and protected business workflows, and remove stale public
widgets/3D demos/overlapping styles. Keep navy, blue, cyan, gold and white from the logo;
crisp static text and restrained vector water motion. No new clone or second working copy.
No live data destruction, public deployment, financial activation or outgoing messages.
The full prior source is recoverable through Git; do not duplicate it into served folders.

The bounded staff backend implementation and regression phase is complete. Root now holds the sole-editor role again for frontend integration, paperwork and the verified GitHub checkpoint; requirements_audit is read-only. No commit or push was made by the implementation subagent.

## Active work - separate portals and owner paperwork

Root is sole editor. Staff backend and dedicated staff.html/team.html interfaces are
implemented. Parent and owner use customer.html/admin.html; the legacy platform entry
routes the authenticated role to its own portal. Staff have own details, clock/work hours,
published roster, leave, absence/unavailability notices and private documents only.
Start shift / Finish shift were browser-tested with synthetic records. Completed hours
appear in My hours. Shift notices never edit planned rosters or actual payroll.
Full backend: 204 passed / 2 skipped. Focused staff suite: 12 passed. Static site, login,
logout and private-cache tests pass. No real records, live messages or payments changed.
See STAFF_PORTAL_API.md; new notice routes are /api/workforce/shift-notices and
/api/management/shift-notices with revisioned management review.

Next: owner/parent visual cleanup, owner paperwork library (nine fillable business forms
plus five achievement certificates), confirmed merchandise/flags, provider-only sign-in.
The PDF generator and blank masters are currently separate unfinished additions, not yet
integrated or visually verified. Do not describe them as completed functionality yet.

## Security checkpoint — verified before next feature work

192 Python tests passed / 2 skipped; 11 new focused security regressions included.
20/20 loopback HTTP checks and Python dependency audit passed; mandatory site check passed.
Read SECURITY_REVIEW_2026-09-13.md for findings, changes and residual scope. GitHub repository
secret scanning, push protection and dependency security updates are now enabled (API
verified). Source remains on codex/fresh-brand-rebuild; no public deployment or live money.

Latest owner clarification: work hours belong in the STAFF portal. Management creates/edits
rosters; staff can only view their own roster, edit own details, clock, request leave, and
upload own medical/professional certificates. Implement both API and UI restrictions.
Google/Apple-only production sign-in still needs explicit account-link invitation flow;
currently unsafe automatic linking to an existing email is blocked. Source image private
costs/ratings/third-party partnership claims must not enter public assets or source seeds.
Shop range has 25 public SKUs after backpack/zipped-tote deduplication, 7 uniforms private.
TSIRC written flag reproduction permission is required before including that flag image.

## Fresh 1 — public rebuild implemented and verified

The 16-page public/sign-in rebuild is implemented on `codex/fresh-brand-rebuild`.
Read `FRESH_REBUILD.md` for removed components, preserved workflows and exact verification.
Seven Node suites and mandatory static checks pass. Backend: 181 passed / 2 skipped.
Browser: 15 public pages at 390px without overflow; matcher handoff, general contact,
synthetic enquiry `HV-ENQ-0030`, collection search/dialog, saved motion and family sign-in
verified. Synthetic preview records stay in ignored `data/local-preview/`.

Important worker fix: encoded API paths cannot enter navigation caches; only public HTML
is cached, private/no-store is respected and operational APIs are network-only. Cache
revision 29 retires earlier runtime and indefinite public-data caches. Do not restore the
old API fallback behavior. New tests cover this explicitly.

Only root edits. The protected operations workspace still uses its existing foundation;
its full visual migration is next. Public site/sign-in no longer load legacy themes or
public support/experience demos. Mobile remains paused. No deployment, live messages or
transactions are approved. New backend public allowlist includes child-safety.html.
Local preview has been restarted with the isolated launcher on 127.0.0.1:8772.

Fresh checkpoint `57699b8` is pushed. GitHub run `34703854753` passed website,
backend, dependency audits and PostgreSQL jobs. The final icon-size correction uses
site.css Fresh 2 / worker 29: generated sign-in icons now have explicit dimensions.
Browser checks at actual 320px cover home/programs/venues/enquiry/shop/child safety and
sign-in without horizontal overflow; mobile menu opens and Escape closes it. The
viewport control affects the selected tab; inspect that tab, then reset before finishing.
The normal preview has been restored. No real customer or financial records were changed.

## Previous checkpoint — UI25 rendering quality

Andrew then reported pixelation and asked for premium quality. Root removed the coarse
WebGL layer from the homepage (its antialiasing was off and DPR capped at 1.5), stopped
whole-card pointer tilting and all text reveal transforms, disabled synthetic font weight,
and removed unnecessary backdrop compositing from text surfaces. Hero photography now
uses a less aggressive 4:3 desktop / 1.15 mobile crop, preserving more source detail.
Metadata and card paragraphs are larger. Logo animation starts fully visible even in a
background tab and its slow float uses whole-pixel increments. CSS/SVG water still moves.

UI24 `fcc481c` is pushed. UI25 uses new asset/cache versions and continues on the same
branch. Preview tests must reset viewport overrides; old browser tabs can retain unusual
sizes, so judge sharpness using a fresh tab at the normal preview size as well. Browser
checked the current font is loaded, hero text opacity 1 / transform none and canvas count 0.
Do not describe this as every production test or every master-brief feature completed.

## Previous checkpoint — UI24 brand colour and motion

Andrew rejected the green/teal direction and explicitly requested the colours of the
existing logo, an animated/moving logo and a moving background. The interface now uses
HV navy `#061A3B`, ocean blue `#008CCB`, cyan `#19C8F4`, gold `#FFC928` and white.
The supplied logo artwork remains intact. A 1.7-second arrival and gentle 6-second float
animate its presentation; two CSS background layers add flowing blue water. The existing
optional WebGL hero is more visible. A visible 44px motion control shares the saved pause,
OS reduced-motion and hidden-tab behaviour with existing controls. Mobile controls are
spatially clear of the booking bar and hidden under navigation/cart overlays.

Cross-page review corrected dark-theme contrast in program comparison/checklists,
enquiry choices/review/success, support dialogs, About cards, venue tables and shop
controls. A synthetic four-step enquiry completed locally as `HV-ENQ-0029`; no outgoing
message or payment was sent. Its test address is reserved `example.com`. Runtime records
stay ignored. See `DESIGN_MOTION_UPGRADE.md` for scope and evidence.

The original logo download is `assets/hv-swim-logo-v3-master.png` (transparent master),
with the smaller website PNG at `assets/hv-swim-logo-v3.png`. Both were linked to Andrew.

The UI22 GitHub checks passed independently: run `34700306682`, website/backend/PostgreSQL.
The wider master brief below is still unfinished; do not call this a complete rebuild,
public launch, full accessibility certification or independent penetration test.

## Previous checkpoint — UI22 operations and security foundation

Andrew authorised all six operational improvements, security/legal hardening and then
provided the full master rebuild brief. **Bendigo, Victoria explicitly reconfirmed**;
ignore the brief's Logan/Queensland assumptions. New visual direction: premium dark.
No domain/hosting purchased. No approval to deploy publicly, send live messages or
activate financial transactions. The one-week sale intention remains ambiguous.

Checkpoint verification: 181 SQLite tests passed / 2 skipped; 137 PostgreSQL contracts
passed / 1 skipped; six Node suites and mandatory static checks passed.

Current additions: dated lesson calendar; held encrypted mail queue with retries and
uncertain-send review; encrypted SQLite/database/upload/key recovery; PostgreSQL adapter
and empty-schema migration with checksums; owner launch-evidence workspace; cookie,
security and accessibility pages and privacy/terms corrections. Full details and test
results are in `OPERATIONS_SECURITY_UPGRADE.md` (maintained during this checkpoint).

Independent read-only reviews found and prompted fixes for raw encryption-prefix input,
OAuth browser binding/local MFA, account-mail approval bypass, chunked request memory
limits, safeguarding-family disclosure, calendar billing/removal conflict, retrospective
absence credits and stale browser weather. No independent production pentest has occurred.

### Next up — master brief, not completed

- Finish focused security/operational regression evidence and browser checks; retain exact
  commands/results in the upgrade report. Add PostgreSQL CI and full uploaded-file recovery.
- Continue deep portal-state visual QA using the confirmed blue/gold dark palette; public
  enquiry, support, program comparison and first-lesson contrast checks are complete.
  Some older low-priority portal states may still contain legacy surface colours.
- Extend enquiries with immutable notes/call events, consent evidence and registration
  resource versioning/secure expiry-aware manual issue/copy workflow; reuse support messaging.
- Scheduled management announcements/ticker/archive; bounded CMS for programs, FAQ,
  parent information, approved acknowledgement and child-safety material.
- Victorian child-safety section, private review/complaint workflows, policy approval and
  processor/retention register. Torres Strait flag reproduction requires prior written
  TSIRC permission: do not download/publish the artwork until rights are recorded.
- Privacy-first optional analytics only if justified by actual business need; current
  inert CTA attributes are not analytics. No advertising tracking exists.
- Responsive/keyboard/reduced-motion/browser functional verification; actual Safari/iPhone
  and VoiceOver verification remain unavailable locally unless a suitable surface is present.
- Final update README/environment/deployment/one-week handover checklist, commit and push
  every verified update. Never present drafts as legal compliance or claim bulletproof security.

## Previous work — UI21 launch preparation

Andrew selected all five next steps and confirmed no domain or hosting account yet.
Repository visibility is now PUBLIC by Andrew's action. Continue pushing verified source;
never push credentials, runtime databases or personal records. Historical private-repo
references below describe earlier sessions.

- Full-database management enquiry search/filtering and 25-record page navigation.
- Minimal enquiry email drafts and local synthetic preview generator; no sending adapter.
- Provider-neutral hosting and launch sequence: `deploy/LAUNCH_PREPARATION.md`.
- Real photos, private pricing, term/arrival details and service accounts remain owner inputs.
- Main is an ancestor of the build branch; this release brings the verified source onto main.
- 160 backend tests passed locally / 1 existing skip. GitHub caught an existing invoice
  test using UTC today after Melbourne midnight; the test now uses Melbourne today. New coverage verifies complete enquiry
  pagination, literal search, offset clamping and safe email draft composition.
- Browser verified 27 synthetic matches across two pages with next/previous controls.
- Owner-supplied registration details match the site; see BUSINESS_DETAILS.md.
  Andrew explicitly has not bought a domain; the listed mailbox remains unverified.
- Isolated preview contains 27 labelled QA Pagination Preview records plus the earlier
  QA journey enquiry. These are fictional local records only.

## Repository information update

Andrew reaffirmed that verified work must always be uploaded to private GitHub.
Updated the repository About description and topics, plus the current branch README,
to describe the website, protected portals, enquiry workflow and gated integrations.
Historical note: the default branch remained `main`; the latest build then was `codex/sunlit-rebuild`. Current work is `codex/fresh-brand-rebuild`.
No public deployment or visibility change is part of this metadata update.

## Latest release — UI20 family journey and enquiry follow-up

Read `FAMILY_JOURNEY_UPGRADE.md` for changes, verification and remaining limitations.
Branch remains `codex/sunlit-rebuild`; sole copy remains `~/Developer/HV-Swim-School`.

- Shared readiness-aware matcher, exact age handoff and first-lesson checklist.
- Management ownership/actions/dates/filtering with audited revision-conflict protection.
- Family shortcuts and clearer lesson-first hierarchy; corrected matcher contrast.
- Additive enquiry migration runs on startup. Older clients without a revision now
  receive validation errors; reload UI20 before editing enquiries.
- 153 Python passed / 1 existing skip; six Node suites and static checker passed.
- Preview at loopback 8772. QA enquiry HV-ENQ-0001 is synthetic, with a test follow-up.
- Real-content inputs listed in `CONTENT_CAPTURE_BRIEF.md`. No messages, payments or
  public deployment performed. Provider delivery and production migration remain open.

### Next up

Review the journey with Andrew, collect approved real content, and select the production
architecture/provider setup from `SUNLIT_REBUILD.md`. Before high-volume use add server
pagination for enquiries; the current view discloses its 250-record loaded limit. Follow-up
dates are internal reminders only. Do not activate live services without approval.

## Previous release — UI19 sunlit rebuild

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
