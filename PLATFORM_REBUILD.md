# HV Swim platform rebuild

Starting source: `406306a0628cbd3ba8e36e724d4165465b9f2465` on the reversible
`codex/platform-rebuild-20260906` branch. Local source and private GitHub were
compared on 6 September 2026. The V5.1 mirror is not the implementation target.

## Implementation plan

1. Audit current routes, permissions, persistence and baseline tests.
2. Extend the existing time-entry ledger with exact durations, explicit breaks,
   retries, approval/correction history, period reporting and immutable exports.
3. Extend existing accounts with scoped management, invitations, recovery and MFA.
4. Integrate the workflows into the existing portals and refine the shared aquatic
   presentation without changing the logo, enquiry-first flow or payment routing.
5. Verify isolated end-to-end journeys, document migration and deployment limits,
   then commit and push verified source. No live financial transmission for testing.

## Initial source findings

- Public pages and all three portals already share the UI16 design system.
- Customer booking creation is already restricted to admin in the actual API.
- Clock actions already use `BEGIN IMMEDIATE` and an open-shift uniqueness index.
- Breaks are accumulated as rounded minutes; clock-out rounds hours to 2 decimals
  and leaves a draft. This needs exact duration and automatic submission.
- Staff time-entry lists are limited to 100; accounting must query the entire ledger.
- Legacy timesheet CSV exports all statuses and has no persistent batch snapshot.
- Account suspension and password changes revoke sessions, but invitation/recovery,
  manager assignment and MFA are missing.
- Xero invoice reconciliation exists. AU payroll transmission is intentionally locked.
- Managed PostgreSQL is a deployment requirement, not an implemented database adapter.

## Scope boundaries

Keep current Manrope typography, approved V3 logo, navy/cyan/gold branding, family
medical privacy, staff-only uniforms and membership-artwork gates. Mobile apps remain
paused. Existing source restoration recovered no private business database. Use an
isolated development database for this work, never existing customer or staff data.

The OpenAI documentation confirms the requested `gpt-6-astra` model identifier;
this running agent cannot switch its own model. No OpenAI dependency is added.

Xero references reviewed for the accounting boundary:
- https://developer.xero.com/documentation/api/payrollau/timesheets
- https://developer.xero.com/documentation/api/payrollau/integration-guide

## Implemented changes

UI18 applies the approved navy/cyan/gold palette across the existing shared design
system. The homepage combines the preserved interactive CSS pool with a separate
4,982-byte optional WebGL water mesh, bounded mobile geometry and rendering resolution,
offscreen/hidden-tab suspension and static failure/reduced-motion fallbacks. Core
headings and enquiry actions remain ordinary HTML. No image/logo replacement or new
front-end framework was introduced. Account pages retain a quieter task-focused layout.

The integrated staff workday and accounting workspace now use the real database:
exact seconds, explicit paid/unpaid breaks, automatic submission, scoped review,
rejection/resubmission, audited corrections, reapproval and immutable export batches.
Existing manual entry remains available but cannot overwrite clock or exported data.
New accounts extend the same users/sessions/CSRF model with invitations, recovery,
assigned managers, MFA and session revocation. See `WORKFORCE_OPERATIONS.md` for rules,
migrations, permissions, backups and the locked live-provider boundary.

## Route coverage inventory

`Local` means exercised using isolated development records, not a claim of live
business data or production certification. Shared styling and valid URLs are preserved
across all 19 HTML files. All primary public pages received responsive browser checks.

| Public route | Purpose and source | Status / verification |
|---|---|---|
| `/`, `index.html` | Approved content; public settings/classes/conditions APIs | Local; interactive scene, navigation, mobile layout, failure-guard tests |
| `programs.html` | Program pathway, matcher, published class API | Local; enquiry-only links and class-fit flow retained |
| `about.html` | Laura-led approved business/teaching content | Local; layout and links |
| `locations.html` | Venue API, dated staff water readings, cached weather adapter | Local; stale reading boundaries; commercial weather/sensor setup still required |
| `shop.html` | Public catalogue API, approved Shopify launch gate, concept products | Local browsing; real checkout needs approved Shopify configuration |
| `enquire.html` | Guided enquiry into protected enquiry database | Local; validation/API tests and responsive form; browser general-question submission verified in management inbox; no customer self-booking |
| `login.html` | Existing sessions/OAuth plus recovery and fragment activation | Local password flow and automated lifecycle tests; email/Google/Apple setup required |
| `platform.html` | Same role-guarded portal shell | Local; full primary route matrix below |
| `customer.html`, `staff.html`, `admin.html` | Existing entry links to role-context login | Preserved; role is determined by account, not selected URL |
| `privacy.html`, `terms.html`, `photo-consent.html` | Existing approved policy copy | Local layout/link checks; final professional policy review still required |
| `offline.html`, `404.html` | Offline/error fallback | Preserved static fallback; private API mutations never cached/queued |
| `START_HERE.html` | Development preview entry and account guidance | Development only; production route blocked |
| `app.html`, `mobile-shell.html` | Paused mobile source | Retained on disk; backend returns 404, no app-store delivery claim |

All portal routes below are fragments on `platform.html`. Menus are convenience,
not access control: API roles, ownership and manager assignments remain authoritative.

| Family route(s) | Purpose / data and boundary | Status |
|---|---|---|
| `#overview` | Own family/lesson summary | Local; laptop/small-phone browser checks |
| `#classes` | Public class browsing → enquiry | Local; API self-booking rejection retained |
| `#bookings` | Existing own confirmed lessons | Local; management alone confirms arrangements |
| `#billing` | Own lesson invoice ledger and Xero references | Local ledger; live provider/payment verification outstanding |
| `#absences` | Own absence records and term credits | Local; existing policy/rules tests retained |
| `#swimmers` | Own child identity, allergy/health and safety fields | Local; encryption/ownership regressions retained |
| `#achievements` | Own swimmer progress and certificates | Local; append-only skill/award tests retained |
| `#incidents` | Family-authorised incident disclosures | Local; private/internal-note boundary retained |
| `#messages` | Own asynchronous support tickets | Local; no fake live-chat or delivery claims |
| `#shop` | Public/family merchandise only | Local browsing; Shopify configuration gate |
| `#notifications` | Own notices and reminder preferences | Local records; off-device delivery setup required |
| `#security` | Own profile, sessions, MFA | New integrated page; API security tests |

| Staff route(s) | Purpose / data and boundary | Status |
|---|---|---|
| `#overview` | Own workday, persisted shift, roster and checks | Upgraded; browser start/break/finish/reopen journey verified |
| `#register`, `#roster` | Authorised published lessons and own roster | Local; existing attendance/roster regressions |
| `#pool` | Staff water reading and opening checklist | Local; timestamps and validation retained |
| `#incidents` | Incident reporting and staff/family IDs | Local; existing encrypted/internal fields and close-review controls |
| `#tickets` | Authorised support queue | Local; staff reply/assignment permissions |
| `#achievements` | Swimmer milestones and certificates | Local; existing certificate/profile access |
| `#timesheets` | Own exact shift/break ledger | Rebuilt; full report API and browser journey |
| `#manualhours` | Existing daily/weekly manual entry | Preserved; cannot mix/overwrite clocked or exported records |
| `#qualifications` | Own certificate/license documents and expiry | Preserved; protected upload/download tests |
| `#merch` | Private staff uniform catalogue | Preserved; public exclusion/API tests |
| `#notifications`, `#security` | Own notices and account protection | Local; shared role boundary |
| `#accounting` (assigned managers only) | Assigned workers' reviews and approved batches | New; automated isolation/self-approval/export access tests |

| Management route(s) | Purpose / data and boundary | Status |
|---|---|---|
| `#overview` | Operational database summaries and action queue | Local; operational CSV clearly distinct from approved hours |
| `#tickets`, `#enquiries` | Family follow-up queues | Local; existing enquiry/ticket state transitions |
| `#enrolments`, `#accounts` | Authorised confirmations, stable family/student/worker IDs | Local; enquiry-first/record-preservation tests |
| `#incidents` | Incident register and reviewed closure | Local; encrypted notes and authorisation tests |
| `#terms`, `#register`, `#roster`, `#classes` | Term/calendar, attendance, scheduling and capacity | Local; original operations preserved |
| `#timesheets` | Full accounting hours, review, corrections and batches | Rebuilt; browser approve/export verified; no automatic payroll |
| `#achievements`, `#compliance` | Swimmer certificates and protected staff documents | Local; retained workflow/access tests |
| `#billing` | Reviewed lesson invoice workflow, Xero reconciliation | Local; provider requests controlled in tests only |
| `#integrations` | Connection/readiness status | Local; live credentials and payroll import still required |
| `#merch` | Premium POD/specialist/embroidered merchandise administration | Local; supplier IDs, rights and sample approval gates retained |
| `#website`, `#locations` | Public content and venue/condition control | Local; sanitisation and publication boundaries |
| `#associations` | Authorised membership evidence/artwork gate | Local; expired/unverified marks fail closed |
| `#notifications`, `#audit` | Notice publishing and operational audit | Local; external delivery not fabricated |
| `#team`, `#security` | Invitation, recovery, scoped access, calendars and own security | New; role/session/MFA tests and browser layout checks |

## Verification record

- Fresh baseline: **128 passed, 1 skipped** Python tests.
- Expanded backend: **151 passed, 1 skipped**; two upstream test-client deprecation
  warnings remain. One existing capacity test is skipped when its seed data contains
  no full class; the new workforce and identity tests do not use live-provider skips.
- Added final regressions for cross-week overnight/manual conflicts, historical
  duplicate approval/export protection, editable own drafts and adjacent day boundaries.
- `npm test`: static checks plus interaction, WebGL fallback, date, login and logout
  regressions. Static coverage: **19 pages, 16 precached files, 11 scripts**.
- Existing read-only live smoke suite: **53 checks passed** against isolated port 8769.
- HTTP security baseline: **20/20 passed**. This is not an independent penetration test.
- Public browser matrix: 10 pages at **320, 768 and 1440 px**, all with a heading,
  no document-width overflow and no broken loaded images. Additional 390 px spot checks.
- Management matrix: **23 routes at 1280 and 390 px**, no reported page errors or
  document overflow. Family: **12 routes at 1024 and 320 px**, same checks. Staff:
  **13 routes at desktop and 390 px**, plus phone clocking/navigation checks.
- Browser console checks returned no errors/warnings for those journeys. These checks
  are not a WCAG certification or a physical-device/GPU performance benchmark.
- Browser test shift: 179 elapsed seconds, 10 unpaid-break seconds, 169 worked seconds;
  automatically submitted, separately approved and frozen in export batch #1. Only
  the isolated development database was changed; no payroll/invoice/payment sent.
- General-enquiry browser journey: required-field feedback, invalid-email response,
  successful submission, matching management reference/message, and closure all verified
  with labelled sample data. No email was sent. General questions now use direct contact
  wording, and the inbox hides irrelevant swimmer/trial fields while retaining lesson
  preferences and workflow. Its 390 px layout was rechecked after this refinement.
- Sample export API journey: **43,254 approved seconds = 12.015 hours**, matching CSV
  and XLSX. Both sheets imported/rendered for visual review with the spreadsheet skill.
- The backup helper successfully created an integrity-checked copy of the isolated
  preview database. A real production backup/restore drill remains a launch requirement.

## Performance and build boundaries

The WebGL layer adds no library bundle or texture download and loads only on the
homepage. It caps pixel ratio at 1.5, simplifies the mobile mesh and skips reduced
motion/save-data/low-memory contexts. The renderer targets at most 30 draw passes per
second, but no measured device frame-rate claim is made. Existing responsive images,
local font, lazy below-fold media and ordinary HTML content remain.

A representative localhost HTTP sample returned the 31,020-byte homepage in
5.918 ms (first byte 5.624 ms) and the 4,982-byte scene script in 4.514 ms.
These are local server delivery measurements, not a production-network page-load
or mobile GPU benchmark; real-device/Lighthouse validation remains a launch step.

Both `pip_audit -r requirements-dev.txt` and `pnpm audit` finished with **no known
vulnerabilities found**. Fourteen initial development-tool advisories were resolved
through narrowly pinned tar 7.5.22, sharp 0.35.4 and uuid 11.1.1 overrides. Asset-tool
help and Capacitor CLI startup passed. One upstream glob deprecation remains; native
mobile builds remain paused. Sources: the maintainers' GHSA-r292-9mhp-454m,
GHSA-f88m-g3jw-g9cj and GHSA-w5hq-g745-h8pq advisories. No web runtime dependency added.

Development asset caching was repaired so local previews no longer stay on old
immutable UI files. Production retains versioned long-cache assets and revalidated
HTML. Private API responses remain no-store and outside service-worker public caches.
This static/FastAPI build has no React/TypeScript compilation; native iOS/Android
builds were deliberately not run while the app phase is paused.

Before production, complete the concrete deployment and integration checklist in
`WORKFORCE_OPERATIONS.md`. The current result is a tested local rebuild, not a launched
site, recovered private database, or connected payroll deployment.
