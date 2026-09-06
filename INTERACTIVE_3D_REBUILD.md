# HV Swim — interactive 3D visual rebuild

Delivered 6 September 2026. API release 5.13.0, presentation revision `5.13.0-ui16`.

## What changed

- Rebuilt the homepage around a bright cream, navy, aqua and warm-gold composition,
  retaining the supplied HV Swim identity, business copy and management-editable fields.
- Added a multi-plane CSS 3D pool with water-light animation, ripples, floats, a branded
  poolside sign, mouse/touch rotation, arrow-key control, reset and three program selectors.
  It is labelled as an illustration rather than a venue plan. Program selections link to
  the real program sections and never create bookings.
- Rebuilt the shop hero with a 20-face rotatable bottle, branded front/back, three colour
  studies, keyboard controls and reset. The object is an explicitly non-orderable design
  concept, not a claim about a real supplier's specification or available variants.
- Applied a consistent design across public pages, legal/supporting pages, sign-in and
  family/staff/management workspaces. Refined typography, cards, forms, navigation, section
  spacing, tables, contrast, button feedback and mobile layouts.
- Put legacy CSS in one cascade layer so the new presentation has explicit precedence,
  without a growing chain of specificity overrides. Existing layout and workflow rules
  remain available beneath the new visual system.
- Added pointer-responsive card depth, a reading-progress line and a persistent motion
  preference. OS reduced-motion preferences always take priority. Decorative animations
  stop when offscreen or the tab is hidden. Pause disables entrance animations completely
  so content cannot be stranded partly transparent.
- Removed the staff-uniform campaign image and staff-merchandise promotion from the
  homepage. Uniform ordering remains in the protected staff/management workflows.
- Preserved enquiry-first enrolment, Xero lesson billing, Shopify merchandise checkout,
  qualification-artwork approval gates, consent-based Facebook content, child/family
  records, alerts, messages, certificates and existing operations. The app stays paused.

## Functional fixes found during browser review

The working-hours screen crashed on legacy entries with full clock timestamps but no
`work_date` or `week_start`. The date helper appended another time suffix, producing an
invalid date. The shared formatter now accepts both date-only values and full timestamps,
including Melbourne timezone conversion, and handles missing/invalid dates gracefully.

Machine-readable business dates now use `Intl.DateTimeFormat.formatToParts` rather than
assuming that a locale's display format is ISO. Payroll-week arithmetic uses UTC calendar
dates, keeping Monday–Sunday stable across browser timezones and daylight-saving changes.
Changing the payroll week now updates all seven daily input labels and submission dates;
non-Monday values are rejected. An isolated preview test saved a 1.25-hour daily draft for
24 August against the selected week and confirmed the returned record. Nothing was
submitted to payroll or sent to Xero.

Also fixed the low-contrast sign-out button on the new light header and replaced the
staff role's outdated app label with “Staff workspace”.

## Verification

- Python suite: **128 passed, 1 skipped**. Two existing upstream deprecation warnings
  remain (Starlette/httpx TestClient and AnyIO BlockingPortal).
- Node regressions: login, logout, 3D input bounds/reset/cancellation, native touch scroll,
  motion preference, restricted browser storage, legacy dates, Melbourne DST and payroll
  calendar boundaries all pass. New tests are included in GitHub CI.
- Static checker: **19 pages, 16 precached assets, 9 scripts**, all pass.
- Public responsive matrix: **49 checks**, seven routes at 320, 375, 390, 430, 768,
  1024 and 1440 px; no horizontal overflow or broken visible images.
- Final portal matrix: **86 checks**, 21 management, 11 staff and 11 family routes at
  320 and 1024 px; correct signed-in roles, expected routes, rendered headings and no
  page-level overflow or failed views. The initial timesheet failures were corrected and
  the final matrix was rerun.
- Supporting pages: **12 checks** across privacy, terms, photo consent, Start Here,
  offline and 404 pages at 320 and 1440 px, all pass.
- Real browser interaction checks: pool program navigation, rotation and reset, keyboard
  input, motion persistence, bottle colour/rotation, mobile menu/Escape, all three roles'
  sign-in/out, towel filtering and the daily-hours save described above.
- Browser error/warning log: empty at the final portal review.
- Existing live smoke suite: **53 passed**. HTTP security baseline: **20/20 passed**.
- Git whitespace/diff checks and JavaScript syntax checks pass.

## Performance

No new graphics dependency, external script, 3D model download or raster asset was added.
`assets/experience.css` is 31,377 bytes (7,914 gzip); `assets/experience.js` is 8,904 bytes
(2,990 gzip). Combined compressed addition is approximately 10.7 KiB. These are measured
asset sizes, not a Lighthouse score. The renderer requests frames only after input;
decorative water animation uses CSS transforms and pauses outside the viewport.

## Source and runtime boundaries

The expected local Developer folder was missing at the start of this session. Restored
the exact private GitHub main commit `676094ff874af6c2bd6fb5ff98fef979367773bc` into the
previously absent `/Users/u1/Developer/HV-Swim-School` folder. The older V5.1 archive under
the ChatGPT project mirror was inspected but not edited. Only source was restored: no
previous private business database, credentials or uploaded staff/customer files were
present in the restored checkout.

Browser work used `/tmp/hv-swim-3d-preview` with development sample accounts. This remains
a local preview, not a production deployment. The source ZIP excludes runtime records,
credentials, virtual environments and Git internals. Existing integration configuration
and launch requirements remain in `PRODUCTION_HANDOFF.md`; this visual release does not
activate external payment, fulfilment, identity, notification or sensor providers.

## Repeat checks

```sh
npm test
node tests/test_login.mjs
node tests/test_logout.mjs
.venv312/bin/python -m pytest tests/ -q
.venv312/bin/python tests/smoke_test.py http://127.0.0.1:8768
.venv312/bin/python scripts/security-audit.py http://127.0.0.1:8768
```

The existing `scripts/browser-qa.mjs` also provides repeatable route/viewport checking
through agent-browser. This session used the Codex in-app browser for direct visual and
interaction testing, including the additional 3D controls.
