# Handoff — current state

Andrew swaps between Claude and Codex whenever one hits its usage limit.
Whichever agent picks up reads this file **first**, and rewrites it **last**.
Keep it short and current. It is the only place the other agent learns what happened.

---

**Wheel:** Claude
**Last updated:** 2026-08-28 by Claude

## Message to the next agent

Claude and Codex cannot talk to each other directly and neither can see the other's usage
limit. This file is the entire channel between us. Write to it like you are writing to a
colleague who will arrive with no memory of anything that happened here.

Say what you were in the middle of, what you would have done next, and anything that
surprised you. If you were stopped mid-task by a limit, the last commit plus this note is
all the other agent gets.

> Two things bit us today, both now guarded against in `AGENTS.md`: V5.1 was committed
> locally but never pushed, and a fresh clone was later made on top of the working copy
> and wiped uncommitted work. Push early, and never clone over this folder. — Claude

## State

V5.1 (merch studio) is now in this repo and matches the archived Codex build exactly.
GitHub previously held only V5.0 — 27 files were stale and two merch images were missing.

Site, backend, portals, PWA and Capacitor shell are internally consistent: no broken
internal links, no stale references to the departed instructor. The merch catalogue is
nine products at concept stage — no supplier engaged, no real checkout, all prices are
preview prices.

## Done this session

- Made this repo the single working copy; archived the Codex project mirror.
- Restored V5.1 over the V5.0 clone and added the two missing merch studio images.
- Added `AGENTS.md`, `CLAUDE.md` and this file.
- Verified: no broken internal links; departed instructor absent from all site content.

## Next up

1. **Legal pages — the most serious gap in the build.** There is no privacy policy,
   terms, cancellation policy or photo/media consent anywhere, and `enquire.html` already
   collects parent and child details. Draft all four; they still need a lawyer's review.
2. **Image weight.** `assets/hv-swim-logo.png` is 1.2MB and loads on all 16 pages;
   `hero-swimmer.png` is 1.9MB. `merch-collection-v2.png` (2.5MB) and
   `merch-uniform-studio-v3.png` (2.1MB) are referenced nowhere — the `.jpg` versions are
   what the site actually uses.
3. No `robots.txt` and no `sitemap.xml`.
4. Accessibility pass against WCAG 2.2 AA — required by `PRODUCTION_HANDOFF.md`, never done.
5. Merch is blocked on assets, not code: a transparent 300 DPI or vector logo master is
   needed before any supplier sample can be ordered. See `MERCH_PRODUCTION_PLAN.md`.

## Open decisions for Andrew

- Which merch products go first, and through which supplier route.
- Whether Shopify gets connected now or after physical samples are approved.
- Real logo master file — the current asset is website-grade, not print-grade.

## Archived — do not work here

- `~/.codex/.chatgpt-projects/.../hv_swim_v4` — original build location, copied here.
  It can be wiped without warning when a new ChatGPT project task is created.
- `~/Documents/ChatGPT/HV SWIM SCHOOL` — separate older Next.js experiment.
