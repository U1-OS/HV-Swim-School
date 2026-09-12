# HV Swim launch preparation

Status: 13 September 2026. Andrew explicitly confirms no domain has been purchased
and no hosting account is selected. The supplied business document lists
`bendigo@hvswimschool.com`; domain ownership and mailbox operation are NOT verified.
Do not rely on that mailbox for launch until the business controls and tests it.
This is a preparation package, not deployment approval. Nothing here activates a service.

## Prepared and available now

- Website and API source with tested role boundaries, enquiries, portals and financial gates.
- Loopback-only synthetic preview: `preview-local.command`.
- `.env.example` lists application/provider configuration; actual values remain outside Git.
- Enquiry acknowledgement and management follow-up templates in `backend/enquiry_mail.py`.
  Run `.venv312/bin/python scripts/preview-enquiry-email.py` to create fictional `.eml`
  files under ignored `data/local-preview/email-drafts/`. They are drafts, not an email
  queue, scheduler or delivery adapter. No From header, SMTP connection or sending action
  is provided by this command.
- Real-photo requirements and reviewable response wording: `CONTENT_CAPTURE_BRIEF.md`.
- Detailed configuration names and business inputs: `SUNLIT_REBUILD.md`.

## Infrastructure specification to take to the chosen host

The static website and Python API need one HTTPS origin, with `/api/` routed to FastAPI.
The host must support Python 3.12+, process restart, restricted secret configuration,
private persistent storage, TLS, health checks at `/api/health`, access logs with restricted
retention, and separate staging and production environments. Runtime databases, uploaded
certificates, private documents and integration keys must not be served as static files.
The repository's API server already restricts its public file surface; preserve that
boundary when adding a proxy. Do not point a generic public file server at the repo root.

SQLite is the local preview adapter. PostgreSQL and an empty-schema migration are
implemented and contract-tested. Production/staging startup now requires a remote PostgreSQL
URL with sslmode=verify-full, separate deployment keys, a valid HTTPS origin and a clean
database. Choose the managed provider and rehearse migration, PostgreSQL backups/PITR,
private uploads and key recovery before real child, family or payroll records are imported.
The bundled encrypted full-data recovery utility currently supports SQLite only.

## Decisions and owner actions

1. Andrew chooses and registers an available business domain in a business-owned account.
   No domain availability or ownership has been assumed or purchased.
2. Andrew chooses hosting, budget, region and account owner. Record recovery contacts and
   who pays ongoing costs. Do not put passwords or recovery codes in this repository.
3. Agree the production data architecture, retention, backup location and restore objectives.
4. Create staging first with synthetic data. Configure HTTPS, origin, private storage and
   separate session/encryption keys. Run API, browser and recovery tests there.
5. Select a transactional email provider and verify the sender domain. Approve message
   wording and rules, then implement durable queueing, retries, duplicate prevention,
   delivery receipts and manual recovery for uncertain sends. Test in the provider sandbox
   before any real address receives a message. Follow-ups need an agreed owner and schedule.
6. Approve real venue/team photos and operating content. Confirm private prices, terms,
   dates, class capacities, access instructions and the merchandise range. Existing prices
   and claims must not be changed by assumption.
7. Configure Xero/Shopify and optional identity/weather services in a secret store. Keep
   financial activation disabled until the separate reviewed acceptance steps are approved.
8. Rehearse backup restore, role permissions, account recovery, session expiry, service
   outages and secret rotation. Complete independent security/accessibility/policy review.
9. Present the staged release and exact DNS/deployment changes to Andrew for explicit
   public-launch approval. Live financial activation remains a separate decision.

## Current blockers

No domain or host chosen; production database architecture undecided; actual provider
credentials and approved real photography missing. Private tuition price, term calendar,
arrival details and final policies remain unconfirmed. Outgoing enquiry email transport
and reminders are not implemented merely by creating the local draft templates.

No production host, DNS record, payment switch, email delivery or public site was changed.
