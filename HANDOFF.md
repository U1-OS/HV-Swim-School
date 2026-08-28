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
- Content truth pass on the public pages: corrected the address in `privacy.html` (it said
  76b Wood Street; the rest of the site says 76), rewrote the enquiry-failure message which
  told parents to check whether "the local server is not running", replaced the hard-coded
  homepage fallbacks that read "Demo · lessons running" to any visitor when the API is
  unreachable, and upgraded the homepage structured data from a bare `Organization` to
  `SportsActivityLocation` with the real postal address — local search is how a Bendigo
  swim school gets found.

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
