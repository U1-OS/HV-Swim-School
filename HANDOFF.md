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
   hosting until the build is finished, so this is deferred. Then run `node scripts/build-sitemap.mjs https://the-domain`.
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
