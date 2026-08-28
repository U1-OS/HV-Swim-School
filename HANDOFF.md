# Handoff — current state

Andrew swaps between Claude and Codex whenever one hits its usage limit.
Whichever agent picks up reads this file **first**, and rewrites it **last**.
Keep it short and current. It is the only place the other agent learns what happened.

---

**Wheel:** unassigned — claim it when you start
**Last updated:** 2026-08-28 by Claude (Cowork session, now closing)

## Message to the next agent

Claude and Codex cannot talk to each other directly and neither can see the other's usage
limit. This file is the entire channel between us. Write to it like you are writing to a
colleague who will arrive with no memory of anything that happened here.

> The build work has moved to Claude Code running locally in this folder. The previous
> session ran through a cloud bridge that could not push, could not delete files and timed
> out at 45 seconds per command — which is how V5.1 ended up committed but unpushed for a
> day. If you are running locally, none of those limits apply to you: push your own work.
>
> I was partway into adding the missing legal pages when the session ended. The audit
> below is done — it is the expensive part, so do not redo it. Writing the pages is what
> remains. — Claude

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

## Next up — legal pages (highest priority)

There is no privacy policy, terms, cancellation policy or photo/media consent anywhere in
the build, and the site already collects children's personal and health information. This
is the one gap that actually blocks a public launch.

**Audit — what the build collects today.** Write the policy against this, not boilerplate:

*Public enquiry form (`enquire.html`, no account required):*
swimmer first name, age band, confidence level, goal, program interest, preferred class
and days, parent name, email, phone, preferred contact method, free-text experience notes
and support needs.

*Family accounts (`backend/database.py`):*
email, password hash, first and last name, phone. Per swimmer: full name, **date of
birth**, level, **emergency contact**, **medical notes**, and a photo-consent flag that
currently defaults to 0.

*Staff:*
rosters and time entries including **latitude, longitude and GPS accuracy captured at
clock-in**, hours, approval trail, and `xero_timesheet_id`. Qualifications with
**reference numbers** and expiry dates. This is employee location tracking and needs its
own disclosure and a staff-facing explanation, not just a customer privacy policy.

*Security:* `login_attempts` stores email and **IP address** for rate limiting.

*Third parties the code already reaches:* Xero (accounting, payroll employees and
timesheets), Shopify, Printify, Open-Meteo (weather). Disclosure to each belongs in the
policy even though credentials are not yet connected.

**Pages to write** — match the existing shell: copy the `<head>`, `.site-header` and
`.site-footer` blocks from `about.html`, use `.container`, `.section`, `.breadcrumb` and
`.eyebrow`, and reuse the existing `.data-boundary` style for anything Andrew must still
confirm.

1. `privacy.html` — collection, purpose, storage, disclosure to the four third parties
   above, children's data and parental consent, staff location and qualification data,
   retention, access and correction, complaints. Frame against the Australian Privacy
   Principles.
2. `terms.html` — website and lesson terms, with cancellation, make-up and refund rules as
   an anchored `#cancellations` section.
3. `photo-consent.html` — photo and media consent wording, tied to the `photo_consent`
   flag on the swimmers table.
4. Link all three from the footer on every public page, and add a consent line with a
   privacy link to the enquiry form. `enquire.html` currently carries a `.data-boundary`
   note saying final privacy terms are unapproved — replace it once the policy exists.

**Do not invent business facts.** Refund windows, notice periods, retention periods, ABN
and the complaints contact are Andrew's to supply. Mark each one visibly rather than
guessing, and tell him what is outstanding. Every draft still needs an Australian privacy
professional's review before launch — say so on the pages.

## Also outstanding

- **Image weight.** `assets/hv-swim-logo.png` is 1.2MB and loads on all 16 pages;
  `hero-swimmer.png` is 1.9MB. `merch-collection-v2.png` (2.5MB) and
  `merch-uniform-studio-v3.png` (2.1MB) are referenced nowhere — the `.jpg` versions are
  what the site actually uses. Roughly 5MB of avoidable weight.
- No `robots.txt` and no `sitemap.xml`.
- Accessibility pass against WCAG 2.2 AA — required by `PRODUCTION_HANDOFF.md`, never done.
- Merch is blocked on assets, not code: a transparent 300 DPI or vector logo master is
  needed before any supplier sample can be ordered. See `MERCH_PRODUCTION_PLAN.md`.
- `_to_delete/` is an empty leftover folder. Delete it; it is gitignored.

## Open decisions for Andrew

- Refund, cancellation and make-up rules; data retention periods; ABN; complaints contact.
- Which merch products go first, and through which supplier route.
- Whether Shopify gets connected now or after physical samples are approved.
- Real logo master file — the current asset is website-grade, not print-grade.

## Archived — do not work here

- `~/.codex/.chatgpt-projects/.../hv_swim_v4` — original build location, copied here.
  It can be wiped without warning when a new ChatGPT project task is created.
- `~/Documents/ChatGPT/HV SWIM SCHOOL` — separate older Next.js experiment.
