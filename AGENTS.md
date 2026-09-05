# Working agreement — Claude & Codex

This repository is the **single source of truth** for the HV Swim School Bendigo build.
Both Claude and Codex work here. Both read this file. Keep it accurate.

## The one rule

`~/Developer/HV-Swim-School` is the only working copy. Keep it on the Mac's local disk,
outside iCloud Drive, Desktop and Documents. Do not recreate a second copy in Documents.
GitHub remote: `https://github.com/U1-OS/HV-Swim-School` (private).

Do **not** work in `~/.codex/.chatgpt-projects/.../hv_swim_v4` — that folder is a
ChatGPT project mirror and can be wiped and replaced without warning. Its contents have
been copied here and it should now be treated as an archive.

Do not work in `~/Documents/ChatGPT/HV SWIM SCHOOL` either — that is a separate, older
Next.js experiment, not this build.

## Everything lives in the repo

This repo is the whole project. No work in scratch folders, no files parked on the
Desktop, no output that exists only in a chat transcript. Notes, plans, decisions and
generated assets all get committed here, or they do not exist as far as the other agent
is concerned.

## Every session

Start:

    git pull --rebase

Finish:

    git add -A
    git commit -m "<what changed>"
    git push

Pull before you start even if you think nothing changed — the other agent may have
pushed since you last looked. If a pull brings in conflicts, resolve them before writing
anything new.

**Push every verified update to the private GitHub repository.** Keep credentials,
databases and personal records local/private, never in Git history. A commit that is not pushed does not exist for the other agent, and
has already been lost once on this project. Do not end a session on an unpushed commit.

## Handoff

Andrew swaps between Claude and Codex whenever one of them hits its usage limit, so a
session can end abruptly and mid-task. Work accordingly:

- Read `HANDOFF.md` **before** you touch anything. Rewrite it **before** you finish.
- Commit and push in small increments as you go, not in one lump at the end. Assume the
  session may stop without warning.
- Never leave the tree dirty or a change half-applied across files. If you must stop
  mid-way, commit what works and write the remainder into `HANDOFF.md` under "Next up".
- Only one agent edits at a time. The `Wheel:` line at the top of `HANDOFF.md` records
  who has it. Set it to yourself when you start; Andrew has the final say.
- Neither agent can see the other's usage limit or notify Andrew when one runs out.
  There is no live channel between Claude and Codex — `HANDOFF.md` is the only way you
  reach each other, so a session that ends without updating it is a session the other
  agent cannot pick up from.

## Never re-clone over this folder

The working copy has been destroyed once by cloning the remote on top of it. If the
folder already exists, use it. Never clone into it, and never resolve a divergence by
replacing local work with a fresh clone without checking what is only local first.

## Check before you commit

    node scripts/check-site.mjs

It takes a second and needs nothing installed. Every check in it exists because that exact
fault was found in this repo: a service-worker precache list that had drifted (one wrong
entry makes `cache.addAll` reject and the PWA silently stops installing), an asset version
bumped in the pages but not in the worker, a stylesheet class that was never written, a
script reaching for elements that no longer existed, and manifest icons that were missing.

If you rename or add an asset, run it. If it fails, fix the cause rather than the check.

## Commits

Small and focused, one concern each. Present-tense summary line describing the change,
not the version number. Do not amend or rewrite commits the other agent made, and never
force-push `main`.

## Never commit

`.env`, `.venv/`, `node_modules/`, `www/`, `*.zip`, `data/*.db*`, `__pycache__/`, build
output, or the versioned `hv_swim_bendigo_*.zip` release archives. `.gitignore` already
covers these — check `git status` before committing rather than trusting it blindly.

## What this project is

Static HTML/CSS/JS site plus a Python backend, a Capacitor mobile shell, and a
merch/commerce layer. No build step for the site — the `.html` files at the root are
served directly.

    index.html, about.html, programs.html, locations.html,
    enquire.html, shop.html                     public site
    admin.html, staff.html, customer.html,
    login.html, platform.html                   portals
    app.html, mobile-shell.html, mobile/        mobile app shell (Capacitor)
    assets/                                     css, js, images, icons
    backend/                                    Python API (server, database, integrations, security)
    scripts/, tests/                            build helpers and smoke tests
    service-worker.js, manifest.webmanifest,
    offline.html                                PWA

Read `README.md`, `PRODUCTION_HANDOFF.md`, `MOBILE_APP_README.md` and
`MERCH_PRODUCTION_PLAN.md` before changing anything structural.

## Business context

Boutique swim school in California Gully, Bendigo VIC. This is paid client work, not a
demo — build it to that standard.

Current scope includes the public website, role-protected operations portals and branded
merchandise. The mobile app is paused. Enrolment begins with an enquiry; staff confirm
placement. Lessons route through Xero, merchandise through Shopify, and uniforms stay
inside protected staff/management pages. The client already uses Xero. Live local weather and daily pool
temperatures are wanted on the site.

A former instructor has left the business and has been removed from the site. Do not
reintroduce staff names from older drafts, zips, or the archived build folder — check
against current content before adding any named person.
