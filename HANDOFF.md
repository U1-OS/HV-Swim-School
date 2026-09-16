# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Cursor Cloud Agent (Studio rebuild)
**Last updated:** 2026-09-17 — draft PR #19; CI flake fix on lesson-register test (Melbourne date)

## Current work — clean studio public rebuild

Andrew rejected merged PR #18 Night Water (“it looks shit”). Branch `cursor/clean-bold-rebuild-cadf` from latest `origin/main` (`9f4dcc2`). **backend/ was not touched.** A former instructor stays off the site.

- New `assets/public.css` loaded last on public pages only. Light editorial system: cream paper `#F4EFE4`, HV navy type `#061A3B`, gold CTAs `#FFC928`, cyan as a hairline/link accent. Not a dark overlay on the old layout.
- Deleted `assets/dark-public.css`. Removed the Night Water aurora injection; `experience.js` now sets `data-theme="studio"` and strips leftover `.site-aurora` nodes.
- Homepage photograph is a real image with caption below — no navy gradient over the photo. About hero uses the campaign crop beside the copy.
- Enquiry wizard: gold progress rail, step fade, selected choice cards, `data-current-step` on the form. Continue still validates before advancing.
- Offline page rebuilt on the same light system. Login/portals do not load `public.css` and stay usable.
- Asset query `5.13.0-ui24`. PWA CORE/RUNTIME/PUBLIC_DATA caches generation 26; `public.css` is in CORE_SHELL.
- Copy and business details unchanged (HVS BENDIGO PTY LTD, Wood Street, Laura-led teaching, $22.50). No staff names reintroduced.
- Static server: `python3 -m http.server 3000 --bind 0.0.0.0` (tmux `hv-swim-static-3000`). Chrome on `DISPLAY=:1` stays on `http://127.0.0.1:3000/index.html`.
- After shots: `/cursor/stores/bc-b1f5564c-7e5b-4036-bcec-0b643b33099a/media/clean-rebuild/` (desktop + mobile for public pages, enquire step 2, programs/shop mid-scroll, login).
- CI run 35105771925 failed `test_lesson_register_enforces_assignment_parent_and_photo_rules`: not the CSS branch — `next_occurrence` can equal Melbourne `business_today()` while POST only rejects dates *after* today. Test now posts a weekday strictly in the future; parent/photo assertions unchanged.

### Next up

Andrew review of draft PR https://github.com/U1-OS/HV-Swim-School/pull/19. Shop remains “in preparation” until samples/Shopify. When a production domain is bought, run `node scripts/build-sitemap.mjs https://<domain>`. Do not restore removed staff names. Do not enable live integrations without approval.

## Previous work — Night Water public rebuild (PR #18)

Merged to main, then rejected on look. Dark overlay (`assets/dark-public.css`, aurora, caches generation 25) is what this studio pass replaces. Do not resurrect that skin.

## Previous work — public-site upgrade (PR #17)

Merged to main. In-place public HTML/CSS/JS upgrade; backend not touched.

- PWA: sign-in and role shells are network-only; runtime cache buckets were generation 24 (now 25 on the Night Water branch).
- Accessibility: enquiry errors `aria-describedby`, login recovery `for`/`id`, skip-links `:focus-visible`, table `scope`, decorative marks hidden from AT.
- SEO: relative canonical + `og:url` on public pages (absolute URLs still come from `build-sitemap.mjs` once a domain exists). Portal shells have `noindex,nofollow`. JSON-LD is `SportsActivityLocation` + `LocalBusiness` aligned with `BUSINESS_DETAILS.md`.
- CSS: one `:root` token set from `BRAND_GUIDE.md` (`#061A3B`, `#008CCB`, `#19C8F4`, `#FFC928`).
- Images: photo WebP + JPEG/PNG fallback; logos are lossless WebP. Asset query was `5.13.0-ui22`.

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
The default branch remains `main`; the latest build is `codex/sunlit-rebuild`.
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
