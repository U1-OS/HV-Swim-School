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
2. **Image weight.** `assets/hv-swim-logo.png` is 1.2MB and loads on all 16 pages;
   `hero-swimmer.png` is 1.9MB. `merch-collection-v2.png` (2.5MB) and
   `merch-uniform-studio-v3.png` (2.1MB) are referenced nowhere — the `.jpg` versions are
   what the site uses. Roughly 5MB of avoidable weight.
3. No `robots.txt` and no `sitemap.xml` (the new legal pages should be in the sitemap).
4. Accessibility pass against WCAG 2.2 AA — required by `PRODUCTION_HANDOFF.md`, never done.
5. Merch is blocked on assets, not code: a transparent 300 DPI or vector logo master is
   needed before any supplier sample can be ordered. See `MERCH_PRODUCTION_PLAN.md`.

## Also outstanding

- `_to_delete/` is a leftover scratch folder. Delete it; it is gitignored.

## Open decisions for Andrew

- Refund, cancellation and make-up rules; data retention periods; ABN; complaints contact.
- Which merch products go first, and through which supplier route.
- Whether Shopify gets connected now or after physical samples are approved.
- Real logo master file — the current asset is website-grade, not print-grade.

## Archived — do not work here

- `~/.codex/.chatgpt-projects/.../hv_swim_v4` — original build location, copied here.
  It can be wiped without warning when a new ChatGPT project task is created.
- `~/Documents/ChatGPT/HV SWIM SCHOOL` — separate older Next.js experiment.
