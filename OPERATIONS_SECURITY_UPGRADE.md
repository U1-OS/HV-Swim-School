# Operations and security upgrade — 13 September 2026

Status: local implementation checkpoint, not production approval. UI22.

## Implemented

Dated lesson occurrences account for published terms, closures and one-off cancellation/
replacement dates. Shared by family next lessons, public daily schedules, staff registers,
reminders and new term charges. Existing issued charges are not rewritten: management must
reconcile calendar changes against existing invoices/credits explicitly.

Encrypted enquiry email drafts start held. A bounded local worker captures `.eml` files by
default. Retryable SMTP rejections back off; interrupted/ambiguous deliveries require human
reconciliation. Stable IDs and dedupe keys prevent ordinary duplicate queue creation.
SMTP acceptance is not proof of inbox delivery. Account invitations/recovery also require
production and `HV_EMAIL_LIVE_APPROVED=true`. No mail was sent during this work.

Private SQLite recovery bundles include a transaction-consistent snapshot, uploads and
key material, authenticated encryption, checksums, exclusive file creation and a new-directory
restore. The automated rehearsal decrypts a restored synthetic record using the restored key.
Live database recovery has not been rehearsed because no production database is configured.

PostgreSQL supports the current parameterised DB API, transactional advisory locking,
statement savepoints, migrations and immutable history triggers. The lock serialises writes
at present; load testing and managed-provider acceptance remain required. PostgreSQL health
checks report index/constraint validity, not a physical-storage certification.

SQLite-to-PostgreSQL migration refuses a nonempty schema, snapshots the source read-only,
preserves constraints/history, compares all row values and resets sequences. No live data
was migrated. Keep application keys unchanged when moving encrypted records.

Management launch checks separate owner evidence from measured configuration. Evidence
never deploys or enables providers. Existing expiry and route permissions are enforced.

## Independent local source-review fixes

- Always encrypt raw sensitive text, even when it resembles ciphertext.
- Bind social-sign-in callbacks to the initiating browser; enforce local MFA boundary.
- Bound incoming body memory while reading chunks, rather than buffering unlimited input.
- Gate the older account SMTP path behind explicit live approval.
- Withhold safeguarding incident narratives and notifications from family accounts; omit
  witness details from ordinary family-facing incidents.
- Revalidate restored lessons for instructor conflicts and calculate new charges from
  effective dates; reject retrospective family absence-credit claims.
- Preserve weather observation times and expire stale browser fallback after one hour.
- Record enquiry collection-notice version and time; do not infer marketing consent.
- Remove old active-enquiry deletion and misleading policy/consent claims.

## Verified checkpoint evidence

- Complete SQLite suite: **181 passed, 2 skipped** (existing seed-dependent case and the
  separately exercised PostgreSQL-only migration test). Two upstream test-client warnings.
- PostgreSQL API/operations/identity/workforce/payroll/migration contracts: **137 passed,
  1 existing seed-dependent skip** on a disposable local PostgreSQL instance.
- All six Node regression suites and JavaScript syntax checks passed.
- Static checker: **22 pages, 16 precached files, 12 scripts** passed.
- Browser: cookie preference control confirms completion; management sign-in and calendar
  form load verified; labelled synthetic closure submitted in the isolated preview.
- GitHub adds an independent PostgreSQL16 service job alongside existing backend and
  website/dependency-audit jobs. CI result must be checked after push.
- These are scoped local tests and source review, not a deployed-environment penetration
  test, accessibility certification or a claim that every possible bug has been excluded.

## Remaining external decisions

Domain/HTTPS host and storage region; managed PostgreSQL service; verified mailbox and
SPF/DKIM/DMARC; real registration document and approved lesson agreement; pricing and term
calendar; safeguarding lead/alternative contact; authorised photography; flags permissions;
processor/retention rules; legal review; independent deployed security and assistive-technology
review. No public deployment or live financial/message delivery is approved.
