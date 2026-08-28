# Handoff — current state

Andrew swaps between Claude and Codex whenever one hits its usage limit.
Whichever agent picks up reads this file **first**, and rewrites it **last**.
Keep it short and current. It is the only place the other agent learns what happened.

---

**Wheel:** unassigned — claim it when you start
**Last updated:** 2026-08-28 by Claude

## Message to the next agent

Claude and Codex cannot talk to each other directly and neither can see the other's usage
limit. This file is the entire channel between us. Write to it like you are writing to a
colleague who will arrive with no memory of anything that happened here.

> The build work has moved to Claude Code running locally in this folder. The previous
> session ran through a cloud bridge that could not push, could not delete files and timed
> out at 45 seconds per command — which is how V5.1 ended up committed but unpushed for a
> day. If you are running locally, none of those limits apply to you: push your own work.
>
> The legal pages are now drafted and linked. What they need next is Andrew's answers to
> the twelve flagged business questions, not more writing. The data audit below is what
> they were written from — keep it accurate if the schema changes. — Claude

## State

V5.1 (merch studio) is in this repo, matches the archived Codex build byte for byte, and
is pushed to GitHub. The repo is the single working copy.

Site, backend, portals, PWA and Capacitor shell are internally consistent: no broken
internal links, no stale references to the departed instructor. The merch catalogue is
nine products at concept stage — no supplier engaged, no real checkout, all prices are
preview prices.

## Done in the last session

- Made this repo the single source of truth; archived the Codex project mirror.
- Recovered V5.1 after a fresh clone overwrote the working copy with the older V5.0.
- Added `AGENTS.md`, `CLAUDE.md` and this file.
- Verified: no broken internal links; departed instructor absent from all site content.
- Audited exactly what personal data the site collects — see below.
- Drafted and linked the three legal pages.
- Cut served image weight from ~3.1MB to ~220KB: `hv-swim-logo.png` rebuilt at 400px wide
  (1.1MB to 44KB, master kept as `hv-swim-logo-source.jpg`) and the hero converted to
  `hero-swimmer.jpg` (1.8MB to 174KB, master kept as `hero-swimmer-master.png`). All
  references repointed and the service-worker cache bumped to `hv-swim-v5-shell-16`.
- Added `robots.txt` (portals disallowed) and `scripts/build-sitemap.mjs`.
- First accessibility pass — see item 3 under Next up for what was fixed and what remains.
- Wrote `tests/test_security.py` (verified passing) and `tests/test_api.py` (unrun — see
  the Tests section above). Before this there were 54 endpoints and no automated tests.
- Rendered the site in a real browser for the first time (Chromium, desktop and mobile) and
  fixed what that exposed: `.empty-state` had no CSS at all, so every empty or failed state
  rendered as bare unstyled text; the homepage kept showing a green "Timetable connected"
  badge even when the class fetch had failed; the failure message gave a parent no way
  forward. Also made the reveal observer robust at any element height (`threshold:.11`
  cannot be met by a section taller than the viewport) and added a CSS failsafe so revealed
  content appears even if JS never runs.
  **Note for whoever is next:** I first reported that half the page sections never became
  visible. That was wrong — my measurement was counting elements deliberately hidden at that
  breakpoint. Re-measured against the original code and it was fine. Do not go looking for
  that bug.
- Rewrote every empty and failure state across the public site (`shop.js`, `programs.js`,
  `enquire.js`, `public-api.js`). They now name what happened, make clear it is not the
  visitor's fault and never that classes are full, and always offer a next step. The shop's
  no-results state has a working "Show everything" button that clears the search and filter.
- **Social sharing was completely missing.** No `og:image` on any page and no share image
  in the repo, so every link posted to the HV Swim Facebook page — the business's main
  channel — rendered as a blank grey box. Built `assets/og-share.jpg` (1200x630, from the
  hero with the logo screen-blended the way the site does it) and added the full Open Graph
  and Twitter card set to all ten public pages. `locations.html` and `app.html` had no Open
  Graph tags at all and now have the complete set.
- Added a branded `404.html`. A mistyped address or a stale Facebook link previously
  returned raw JSON (`{"detail":"Not Found"}`). The page now says nothing is wrong with the
  visitor's booking or account and lists the six places they were probably heading.
  `backend/server.py` serves it for browser requests only — the API still answers JSON.
- Added cache headers, which the server was not sending at all. Versioned assets
  (`?v=5.1.0`) are cached for a year as immutable; unversioned assets for a day; HTML always
  revalidates so corrected copy and prices are never served stale. **When you change a CSS
  or JS file you must bump its `?v=` in every page that references it, or returning visitors
  will keep the old one for a year.**
- Fixed a CSS bleed where `.legal-body a` styling applied to buttons, rendering button
  labels as dark underlined text on a blue fill. Affected the legal pages and the new 404.
- Reviewed and fixed the sign-in page, which nobody had looked at. The logo showed a black
  box because `.auth-visual > *` sets `z-index:1`, creating a stacking context that confined
  the `mix-blend-mode:screen` meant to knock the black out. Also rewrote three pieces of
  build copy that were being shown to parents ("Use a demonstration account below, or
  connect real accounts during deployment", a PBKDF2/HttpOnly security note, and
  "Secure production-foundation preview" in the footer).
- Rebuilt the app icons. They were declared `purpose:"any maskable"` but were not maskable:
  the logo ran past the inner 80% safe circle, so Android's circular and squircle masks were
  cropping "HV" and part of "SWIM", and the source art had black letterbox bars top and
  bottom that showed on the home screen. There are now separate `any` and `maskable` sets on
  the brand navy, generated from `hv-swim-logo-source.jpg` with the black knocked out.
  `manifest.webmanifest` also had `id:"/hv-swim-mobile"` against `scope:"./"`, which do not
  match; `id` is now `"./"`.
- Verified the service-worker precache list against the filesystem — all 36 entries exist.
  Worth re-running after any asset rename: a single missing file makes `cache.addAll` reject
  and the service worker never installs, silently disabling the whole PWA.
- Fixed the mobile menu, which was a keyboard dead end: opening it moved no focus, Escape
  did nothing, Tab walked straight out of the overlay to the page hidden behind it, and a
  menu left open across a resize to desktop kept the page scroll-locked. It now moves focus
  into the menu on open, returns it to the toggle on close, keeps Tab and Shift+Tab inside
  while open, closes on Escape, and closes itself on resize. Verified in a real browser at
  390px — focus stayed inside across 30 tab presses and shift-tabbing back.
- Fixed validation feedback on the enquiry wizard. It said "Please complete the highlighted
  field" while highlighting nothing, and never set `aria-invalid`, so a screen-reader user
  got no indication which field was wrong. It now names the field from its label
  ("Please fill in "Swimmer's first name" before continuing"), marks it visibly and via
  `aria-invalid`, and clears both the moment the parent starts fixing it.
- **Protected the public enquiry form**, which was the only unauthenticated write endpoint
  in the system and had no rate limiting and no spam protection whatsoever. Anyone could
  POST unlimited enquiries, each of which also created an admin notification — so a bot
  would have flooded the management inbox and grown the database without limit. There is now
  a hidden honeypot field (bots fill it, people never see it; a hit returns a normal-looking
  success and stores nothing) and a limit of 5 enquiries per IP per hour, whose 429 message
  gives the phone number so a genuine family is never stranded. Added covering indexes for
  both this and the sign-in rate limit, since each runs a scan on every attempt.
- Reviewed the front-end for XSS, since management, staff and families all enter text that
  gets rendered into other people's pages. **Found none.** `platform.js`, `shop.js`,
  `programs.js` and `public-api.js` escape consistently through their `esc()` helpers, and
  the handful of cases a scan flags turn out to be `textContent`, `document.title`,
  `URLSearchParams` values, or arguments escaped downstream by `shell()`. Worth re-checking
  after any new render function, but the pattern in place is sound.
- Extended `test_api.py` from 19 to 28 tests, covering the enquiry honeypot and rate limit,
  the branded 404, that the API still returns JSON for unknown paths, and the cache headers.
  Still unrun — see the Tests section.
- Read through `assets/platform.js` (the 3 portals, ~75KB) and fixed two real defects.
  The staff **"Clock & work location" clock was frozen**: it displays seconds but used
  `setTimeout`, so it ticked exactly once and then stopped — staff timing a clock-in were
  reading a stopped clock. It now ticks on an interval that is cleared when the route
  changes, which also closes a leak where each visit left another interval running against
  a detached element. Second, **a failed session load left the portal on its loading
  spinner forever**: a 401 redirects to sign-in, but a server or connection failure was
  swallowed silently. It now explains what happened, reassures that the account is
  unchanged, and offers retry.
  The rest of the file is in good shape — event delegation is registered once rather than
  per render, geolocation failure is handled, and escaping is consistent.
- **Closed a booking race.** Class capacity was read and then written with no write lock,
  so two families booking the last place at the same moment could both get it — putting the
  class over its instructor-to-swimmer ratio, which is a safety limit rather than a
  commercial one. Term enrolment opening is exactly when that traffic arrives. Both
  `create_booking` and management waitlist promotion now take `BEGIN IMMEDIATE` before
  checking capacity, and two partial unique indexes (`uniq_booking_confirmed`,
  `uniq_waitlist_waiting`) enforce it at the database level as well. The indexes are created
  defensively so an older database holding duplicates cannot block startup — if that
  happens, clear the duplicates by hand and restart.
- Reviewed the payroll path. A forgotten clock-out records every hour in between — a shift
  left open on Friday and closed on Monday books 70-odd hours — and that figure flows
  straight toward Xero. The recorded value is deliberately **not** altered (silently editing
  payroll data would be worse), but a shift over `LONG_SHIFT_REVIEW_HOURS` (12, and Andrew
  should confirm that figure) now raises a management notification and tells the staff
  member it is being checked.
- **Removed ~3.8KB of dead code from `assets/public-api.js`.** The old lesson-finder widget
  and single-page enquiry form were replaced by the four-step wizard in `enquire.js`, but
  their code was left behind pointing at eight element ids that exist on no page
  (`finder-result`, `finder-button`, `finder-age`, `finder-experience`, `enquiry-form`,
  `enquiry-status`, `enquiry-submit`, `enquiry-experience`).
  This mattered more than tidiness: it misled two separate reviews in one session. An
  earlier pass "fixed" an enquiry-failure message in that block that no visitor could ever
  see, and a later pass reported a reflected XSS in it that was never reachable. **If you
  are reviewing a code path, confirm the elements it touches actually exist before drawing
  a conclusion about it.** Verified after removal: no dead element references remain, no
  console or page errors on any page, and the live availability failure state still renders.
- **Service worker was caching failed responses.** Its catch-all handler stored every
  response it saw, including 404s and 500s, so one transient server error could be pinned in
  the cache and served to that visitor from then on. It also tried to cache opaque
  cross-origin responses, which `cache.put` rejects, producing unhandled console errors.
  It now stores only successful same-origin responses.
- Fixed two storage-related faults in `app.js`: a successful weather fetch was discarded if
  writing it to the cache threw (so anyone with site data blocked never saw live weather,
  despite the request having worked), and the demo-reset handler could not complete for the
  same reason. Verified with storage forced to throw: no page errors, site fully usable.
- Swept the whole codebase for stale references after the `public-api.js` discovery: no JS
  references an element id that exists on no page, no front-end call targets a missing
  endpoint, and every `localStorage` access is guarded. The three unreferenced backend
  endpoints (`/api/admin/metrics`, the Xero OAuth callback and the pool-sensor feed) are
  called from outside the browser and are correct as they are.
- Security review of `backend/`. The code is in good shape — SQL is parameterised
  throughout, CSV formula injection was already guarded, exports are role-gated, ownership
  checks are consistent, PBKDF2 is 210k iterations with a constant-time compare, and the
  cookie and CSP settings are sensible. Four things fixed: `login_attempts` was never
  pruned so email/IP pairs accumulated forever (now deleted after 30 days, and the privacy
  policy states that figure); the CSRF token was compared with `!=` rather than
  `hmac.compare_digest`; the CSV injection guard missed tab and carriage-return prefixes;
  and the three redirect stubs carried an inline `<script>` that the app's own CSP blocks,
  throwing a console violation on every visit (the meta refresh already did the work).
- Content truth pass on the public pages: corrected the address in `privacy.html` (it said
  76b Wood Street; the rest of the site says 76), rewrote the enquiry-failure message which
  told parents to check whether "the local server is not running", replaced the hard-coded
  homepage fallbacks that read "Demo · lessons running" to any visitor when the API is
  unreachable, and upgraded the homepage structured data from a bare `Organization` to
  `SportsActivityLocation` with the real postal address — local search is how a Bendigo
  swim school gets found.

## The portals have still never been seen rendered

`platform.js` has now been read line by line, but the family, staff and management
workspaces have **never been opened in a browser** — that needs the FastAPI backend
running, and it cannot be installed from the environment the last session had.
Andrew has asked that nothing be faked or simulated to get around this, which is right:
a mock backend would prove the UI renders against invented data, not that it works.

**Whoever has FastAPI available should run the server and walk all three portals.** It is
the largest surface in the project with no visual review at all.

## Regression sweep — last run 2026-08-28

All 12 public pages (plus 404 and sign-in) rendered in Chromium at 1440x900 and 390x844:
**no JavaScript errors, no console errors, no horizontal overflow, no content left
invisible.** The only console output is `fetch` failing for `/api/...`, which is expected
when the pages are opened straight from disk with no backend running.

One measurement gotcha, since it caught me twice: when checking `.reveal` elements, scroll
in steps well under one viewport with a pause between each and a settle at the end, and
exclude elements that are `display:none` at that breakpoint. Coarse scrolling reports
elements as invisible that are perfectly fine, and responsive variants are hidden by design.

## Tests

There is now a `tests/` suite — see `tests/README.md`. `test_security.py` is **verified
passing** (15 checks, runs with plain `python3`, no pytest needed). `test_api.py` covers
role boundaries, ownership isolation, CSRF and secret leakage but has **never been
executed** — it was written without access to a package index, so `fastapi` could not be
installed. **Whoever picks this up next: run `pytest tests/ -q` first**, fix any fixture
mismatches, and report the result here. Until then treat `test_api.py` as a reviewed
specification rather than a passing suite.

## Next up

**Legal pages are drafted and committed** — `privacy.html`, `terms.html` (with an anchored
`#cancellations` section) and `photo-consent.html`, all linked from the footer of every
public page, with the enquiry form now pointing at the privacy policy and cancellation
policy. Styles are in the `Legal pages` block at the end of `assets/styles.css`.

They are written against what the platform actually collects, not boilerplate. **Twelve
items are marked `HV Swim to confirm` and must be filled in by Andrew before launch** —
run `grep -o 'HV Swim to confirm:</strong>[^<]*' *.html` to list them. The big ones are
fees and payment terms, cancellation notice and make-up rules, retention periods, ABN, and
the privacy contact. Do not guess any of them.

Every page carries a `Review status` section saying it has not yet been checked by an
Australian adviser. Leave that in place until it actually has been.

Remaining work, in order:

1. Get Andrew's answers to the twelve flagged items and fill them in.
2. **Set the production domain** once Andrew buys one — he is staying on the current
   hosting until the build is finished, so this is deferred. **Until it is set, social
   sharing still will not work**: `og:image` is a relative path and Facebook will not
   resolve it. One command fixes that, along with canonical URLs and the sitemap. Then run `node scripts/build-sitemap.mjs https://the-domain`.
   That writes `sitemap.xml` and fills in the `Sitemap:` line in `robots.txt`. Nothing was
   guessed — `HV_PUBLIC_URL` is still `localhost:8765` and no canonical URLs are set on any
   page. Add `<link rel="canonical">` and `og:url` at the same time.
3. **Accessibility — first pass done, but static only.** Fixed: skip links on the nine pages
   that lacked them, heading-order breaks on `locations.html` and `START_HERE.html`,
   reduced-motion support in `platform.css` and `mobile-shell.css` (there was none) plus a
   catch-all in `styles.css`, and 16 secondary-text colours that failed 4.5:1 contrast.
   Alt text, form labels and landmarks were already clean.
   Still needed and **cannot be done statically**: keyboard-only walkthrough of the enquiry
   wizard and the platform portals, screen-reader testing, focus-order check on the mobile
   menu and cart drawer, and confirmation that live-updating regions (pool conditions, class
   places) announce properly. Run these in a real browser.
4. Merch is blocked on assets, not code: a transparent 300 DPI or vector logo master is
   needed before any supplier sample can be ordered. See `MERCH_PRODUCTION_PLAN.md`.

## Also outstanding

- `_to_delete/` is a leftover scratch folder. Delete it; it is gitignored.

## Known and accepted, not bugs

- Sign-in rate limiting is per email + IP. Password spraying — one common password tried
  across many accounts from one address — is not caught by that shape. Worth revisiting if
  real accounts are ever exposed to the open internet, but not a launch blocker.
- The "Demo ·" labels on pool conditions are deliberate: unverified readings are marked
  rather than passed off as live, and they clear once staff verify. Leave them.

## Missing feature — correcting a time entry

Management can **approve** a time entry and nothing else. There is no way to edit, reject
or return one for correction. So a forgotten clock-out that records 70 hours can only be
approved or left sitting, and a staff member who forgot to clock out cannot start their
next shift either — clocking in is refused while an entry is open, with no self-service fix.
The long-shift flag added above makes the problem visible; it does not solve it.

This needs Andrew's decisions before it is built: who is allowed to correct someone else's
recorded hours, whether the original figure must be retained alongside the correction (it
should — `audit_log` already exists for this), and whether a staff member can void their own
open shift or must ask a manager.

## Missing feature — password reset

There is **no password reset anywhere in the build**: no endpoint, no token flow, no email.
A parent who forgets their password currently has no route back into their account. As a
stopgap the sign-in page now offers "Forgotten your password?" as an email to the team, so
the dead end is at least a human one.

Building it properly needs decisions Andrew has to make first — which email provider sends
the reset, how long a reset link stays valid, and whether staff and management accounts
reset the same way or are handled manually. Do not build it blind; it touches authentication.

## Open decisions for Andrew

- Refund, cancellation and make-up rules; data retention periods; ABN; complaints contact.
- **Opening hours are published nowhere on the site.** Parents look for them and they belong
  in the structured data too. Not invented — needs Andrew's actual hours.
- Confirm the public contact details are current: the site uses
  `sloanswimschool@hotmail.com` and 0413 462 112 throughout. An earlier draft of this
  project used a different address and number, so one of them is out of date.
- `START_HERE.html` prints the three demo account passwords. It is disallowed in
  `robots.txt` and the accounts only work in development mode, but the page should not be
  deployed to a public host as-is.
- Which merch products go first, and through which supplier route.
- Whether Shopify gets connected now or after physical samples are approved.
- Real logo master file — the current asset is website-grade, not print-grade.

## Archived — do not work here

- `~/.codex/.chatgpt-projects/.../hv_swim_v4` — original build location, copied here.
  It can be wiped without warning when a new ChatGPT project task is created.
- `~/Documents/ChatGPT/HV SWIM SCHOOL` — separate older Next.js experiment.
