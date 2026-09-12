# Family journey and enquiry follow-up upgrade

12 September 2026 · `codex/sunlit-rebuild` · UI20 / cache suffix 21.

## Delivered locally

- One shared lesson recommendation function powers Programs and Enquire. A technique
  goal alone no longer routes a cautious/supported swimmer to Stroke Development.
  Teen/adult beginners receive private-assessment guidance; individual support remains
  a personal discussion. Staff confirm all placements.
- Seven age choices match the enquiry exactly. Age, confidence and goal carry forward;
  changed answers clear stale matcher results and refresh enquiry recommendations.
- Readable, light matcher styling fixes inherited low-contrast text. Answer summaries,
  keyboard-focusable results and a four-item pool-bag checklist clarify the journey.
- Management enquiries now support an active management owner, next action, follow-up
  date, search and active/new/due/unassigned/closed filters. Reminders are internal only.
- Enquiry writes use a required revision, conditional database update, role/CSRF checks,
  owner validation and audit record. Stale edits return 409 without overwriting data.
  Closing clears the next action/date. General enquiries cannot become trial bookings.
- Family home promotes lessons and direct absence/progress/message/preparation actions.
  The family reference number moves below the main content. Recurring lessons are
  labelled honestly; no unimplemented holiday-aware next-lesson calendar is implied.
- `CONTENT_CAPTURE_BRIEF.md` specifies real photography, operating details and draft
  acknowledgement copy needed from the business.

## Verification

153 Python tests passed; one existing skip and two upstream deprecation warnings remain.
Six Node suites and the static checker passed (19 pages, 16 precached files, 12 scripts).
The restarted preview also passed 53 HTTP smoke checks and 20 security baseline checks.
New regression coverage includes recommendation readiness/age, script loading order,
role/CSRF boundaries, invalid owners/dates, conflicting revisions, persistence, closure
normalisation and auditing.

Browser checks: beginner technique versus independent recommendations, changed-answer
reset, adult guidance, age/confidence/goal handoff, complete enquiry and saved reference,
checklist completion, management assignment/date/action save and reload, due/search/no-
results filtering, family absence/progress/message navigation and desktop/phone layouts.
Programs checked at actual widths 320/390/768/1440; family home at 390 and 1440.
The enquiry inbox was also checked at 560. No document-width overflow in those checks.

Synthetic enquiry `HV-ENQ-0001` in `data/local-preview/` is labelled QA Journey Review /
QA Pathway. It is assigned to the seeded management account for follow-up testing.
No real family details, outgoing communications or financial transactions were used.

## Boundaries still in place

The inbox loads up to 250 enquiries, prioritising new enquiries. Filters apply to that
loaded set; server pagination is still needed before high-volume operation. Management
owners have access to this inbox; staff assignments are deliberately excluded.
No background email/SMS reminder or acknowledgement is sent. External delivery adapters,
provider acceptance tests and production database migration remain outstanding.

Real photos and consent, private pricing, class/venue details, product samples and live
credentials cannot be fabricated. See `SUNLIT_REBUILD.md` for the precise business and
credential checklist. The native app stays paused. Public deployment and live financial
activation still require Andrew’s explicit approval.
