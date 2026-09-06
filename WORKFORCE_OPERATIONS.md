# Accounts, working hours and accounting

## Storage and migration

This release extends the existing SQLite database. There is no PostgreSQL adapter.
`DATABASE_URL` and `HV_DATABASE_URL` now fail startup rather than being silently
ignored. `HV_DATA_DIR` selects the protected persistent directory. This preview is
not approval to store real child, health or payroll records in a public deployment.

Startup runs the existing schema initialisation, then the additive migrations in
`backend/identity.py`, `backend/workforce.py` and `backend/payroll_adapter.py`.
Existing users, memberships, bookings, invoices and time entries are retained.
Existing admins retain owner capabilities. Existing clock totals are labelled
`legacy`; exact break timestamps cannot be recovered from rounded old totals.
An old open shift must be reviewed and corrected, not silently completed. Duplicate
open shifts cause migration to fail closed for operator review.

New tables hold explicit breaks, clock request references, immutable event history,
approved export snapshots, reporting settings, manager assignments, token digests,
encrypted authenticator secrets and per-employee payroll jobs. New columns are
additive; migrations are safe to run repeatedly. Tests exercise restart preservation.

### Backup and rollback

Before upgrading a real instance, stop staff writes and take a consistent backup:

```sh
.venv312/bin/python scripts/backup-database.py /absolute/private/hv_swim.db /absolute/private/backups/pre-ui18.db
```

The command refuses to overwrite, opens the source read-only, uses SQLite's backup
API, creates the destination with mode 0600 and checks integrity. Back up uploaded
certificates and association assets separately. Keep the encryption key in the
secret manager; a database backup alone cannot restore encrypted fields without it.
Encrypt backup storage and rehearse restoration on a separate isolated instance.

Rollback is a coordinated restore of the pre-upgrade database, private uploads,
configuration and starting source commit `406306a0628cbd3ba8e36e724d4165465b9f2465`.
Do not delete columns from a working database or run the old clock writer over new
records. If staff have worked since the upgrade, first preserve the complete new
database and reconcile the post-upgrade events and immutable exports with management.
Never discard or replay exported accounting records as a shortcut to rollback.

## Permission model

| Capability | Family | Staff | Assigned-team manager | Owner/admin |
|---|---|---|---|---|
| Family, child and billing records | Own authorised records | Existing pool-deck access only | Same existing staff boundary | Authorised organisation access |
| Start/finish own shift and breaks | No | Yes | Yes | Yes via workforce API |
| Read working hours | No | Own | Own and assigned staff | All |
| Approve/reject/correct | No | No | Assigned staff, never self | Other workers, never self |
| Freeze/download approved batches | No | No | Entire batch must be within assigned team | All |
| Invite, suspend, reactivate, role changes | No | No | No | Yes |
| Finance, provider settings, audit | Own invoices only | No | No additional finance access | Yes |
| Profile, sessions, authenticator | Own | Own | Own | Own |

Managers remain `role=staff` with `management_scope=manager`. They cannot enter
admin routes or gain authority by editing a request field. Scope is checked in the
database on every request, not trusted from the menu. Removing assignment prevents
future access to that worker and their historical export files. A second owner
must approve an owner's own hours. The last active owner cannot be disabled or demoted.

## Invitation and recovery

Management → Team access & settings creates one-time, 24-hour invitations. Existing
People & accounts controls suspend/reactivate users without erasing their records.
Access changes revoke sessions. Suspension, password reset and role changes also
invalidate outstanding account links. A required temporary-password change is
enforced in the API, not only by the interface.

Invited accounts are inactive until activation. Tokens are random, stored as digests,
single-use and carried in URL fragments that do not enter HTTP request/referrer logs.
The login page immediately removes the fragment from visible history. Private links
must never be posted into public tickets, chat transcripts or analytics.

For actual email submission configure `HV_SMTP_HOST`, `HV_SMTP_PORT` (465 by default),
`HV_SMTP_USER`, `HV_SMTP_PASSWORD` and `HV_SMTP_FROM` in protected environment settings.
The implementation uses certificate-verified SMTP over TLS. It reports provider
acceptance, not guaranteed inbox delivery. No SMTP credentials or live delivery were
available for this rebuild. The alternative is an explicitly labelled private
handover after management verifies identity; it does not claim email verification.

Public recovery always gives the same response and limits requests per email/IP.
Without mail configuration, requests enter the owner recovery queue. Creating a
manual recovery link requires the owner's current password. Security-proof attempts
are limited to ten per 15 minutes per account, including failed attempts.

Account & security supports encrypted TOTP setup, confirmation, replay prevention,
last-login/profile details and revocation of other sessions. Enable MFA for every
owner before launch. Password recovery does not remove MFA. Lost authenticators
require a separately approved and audited operator identity-verification process;
there is deliberately no public or manager bypass or universal recovery code.
Google/Apple family OAuth remains credential-gated. Demo identities cannot log in
in production, and production bootstrap does not seed development accounts.

## Shift and break rules

The main staff screen and Working hours expose Start Shift / Finish Shift, explicit
paid/unpaid breaks, selected workplace and a timer. No GPS or continuous tracking is
collected. Server UTC timestamps are authoritative; the timer uses the server
snapshot and a monotonic browser counter. It is never used to save duration.

Clock requests carry a unique reference. Transactions and the existing unique open
shift index enforce one active shift per person, even across concurrent clients.
A repeated reference returns the original result; conflicting reuse is rejected.
After a lost response the user can refresh to reconcile saved state. Offline actions
are not accepted or silently queued. Logout, browser closure and server restart do
not finish a shift. A configurable long-shift warning does not invent a finish time.

Finishing closes an open break, calculates integer elapsed/worked/break seconds and
automatically submits the shift. Only explicitly recorded unpaid breaks are deducted.
Paid breaks remain in worked time. No award classifications, overtime, automatic
deductions, wages, taxes or payments are calculated by this release.

Review states are separate from export state. Rejection requires a comment; staff
can resubmit with a response. Corrections require an explanation, explicit time-zone
offsets, valid non-overlapping intervals and the current entry version. They retain
before/after timestamps and breaks, actor and reason, and require reapproval.

Exported entries cannot be rewritten. A separately approved signed-second amendment
must reference an actually exported work date. The original file stays reproducible.
Amendments are deliberately blocked from automated Xero preparation until reviewed
as adjustments in the actual payroll system.

## Reporting and exports

Working/accounting hours query the complete ledger rather than the legacy 100-row
screen endpoint. Report by day, configurable week start, fortnight anchor, calendar
month or custom inclusive date range (up to 367 days), worker, venue and approval.
Melbourne day boundaries split overnight shifts and break intervals using actual
elapsed UTC time, including 23/25-hour daylight-saving days.

Manual weekly totals remain Monday–Sunday, as before. They are never arbitrarily
spread across days: a partial reporting period flags the unallocated total and
blocks export. Manual daily totals are labelled, not presented as clock events.
Clock/manual overlaps are rejected, including overnight work that began in the
previous week. Approval and export also recheck historical records for conflicting
allocation periods. Adjacent midnight boundaries are not treated as overlaps.
Legacy rounded hours remain explicitly legacy.

Review approved export → Create approved snapshot freezes entry versions, daily
slices, filters, period, timestamp and creator. Re-download the existing batch after
a lost response; creating it again cannot duplicate included entry/date/version rows.
Export is not payroll transmission. The old admin CSV is labelled **Operational
hours CSV (all states)** and must not be used as an approved accounting file.

CSV guards formula-leading text; XLSX uses typed numeric cells and inline text, no
executable formulas. Seconds are the reconciliation unit. Decimal hours are display
values, not per-shift rounding. Generated accounting notes exclude arbitrary staff
free text so medical/incident details are not copied into payroll exports.

Generate samples without touching the business database:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv312/bin/python scripts/sample-hours.py /tmp/hv-sample-exports
```

The script creates a fresh temporary database, exercises real clock, break, approval
and export APIs, then writes clearly labelled CSV/XLSX files. The three sample shifts
reconcile to **43,254 seconds = 12.015 hours**. No provider is contacted.

## Xero accounting boundary

Lesson invoicing remains with the existing reviewed Xero invoice adapter. Merchandise
and private uniform checkout remain Shopify responsibilities. Neither connection
grants permission to transmit payroll.

The new `backend/payroll_adapter.py` targets Xero AU **2.0** draft timesheets, with
per-employee jobs, tenant/employee/calendar/earnings UUID validation, exact daily
units, durable idempotency keys, immutable source payloads and per-job outcomes.
The official contract reviewed on 6 September 2026 is:

https://raw.githubusercontent.com/XeroAPI/Xero-OpenAPI/master/xero-payroll-au-v2.yaml

Creation requires `payroll.timesheets`; Xero-connected employee/calendar/earnings
resource discovery also requires the applicable employee/settings read scopes.
Review current scopes with the actual organisation before requesting broader consent:

https://developer.xero.com/documentation/api/payrollau/integration-guide

The adapter receives independently verified employee/calendar/rate mappings and a
complete provider-verified pay period. UUID-shaped text entered in an admin form is
not verification. It refuses legacy, unallocated weekly and amendment rows. A matching
organisation, hourly earnings unit and exact complete period are mandatory.

Responses must reconcile employee, dates, every daily line, total hours and provider
IDs. One employee succeeding does not mark others successful. Timeout, malformed
response or mismatched totals enter review; already in-flight/confirmed/uncertain jobs
are not automatically resent. Existing encrypted OAuth storage and serialised token
refresh remain the credential boundary. No credentials enter export/job snapshots.

**Live payroll is intentionally locked.** No web route enables dispatch, and
`XERO_SYNC_ENABLED=true` cannot bypass it. Provider resource import and an operator
reconciliation interface still need implementation against the real organisation,
then controlled provider verification and explicit deployment approval. The tested
adapter alone is not live integration. Review uncertain/in-flight jobs against the
employee period in Xero before any replacement; never manually clear job rows.

## Launch checklist

- Select and approve hosting/database architecture. Do not assume PostgreSQL works.
- Migrate authorised records and rehearse encrypted backup/restore without overwriting.
- Configure HTTPS, persistent storage, encryption/session secrets and a bootstrap owner.
- Enable owner MFA and approve lost-authenticator recovery/retention procedures.
- Configure and test transactional email; confirm sender DNS and inbox delivery.
- Verify Xero invoice mappings, separate payroll readiness and Shopify catalogue rights.
- Review association evidence/artwork, merchandise samples, commercial weather terms
  and real pool readings. App-store delivery remains out of scope.
- Complete independent security, accessibility, privacy and employment-policy review.

Local automated and browser tests are engineering evidence, not a penetration-test
certification, payroll-law approval or a guarantee against compromise.
