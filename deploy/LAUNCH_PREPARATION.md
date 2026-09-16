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

### Reverse proxy and client IP

Production startup refuses to run until `HV_TRUSTED_PROXIES` lists every proxy address
that terminates HTTPS in front of the API (comma-separated IPs or hostnames that resolve
to the proxy). The API reads the leftmost `X-Forwarded-For` hop only when the immediate
peer matches that list, so sign-in throttling, enquiry limits and audit entries keep the
real client address instead of collapsing to the proxy.

Run Uvicorn behind the proxy with explicit header trust, for example:

`uvicorn backend.server:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=203.0.113.50`

Use the proxy's actual address in both `HV_TRUSTED_PROXIES` and `--forwarded-allow-ips`.
Never use `*` for forwarded allow lists. Loopback preview launchers omit these flags because
they bind to localhost only.

`HV_DATA_DIR` must be owned by the service account with directory mode `700` and database or
uploaded document mode `600`; the application sets these modes on startup and after writes.

### Repository deploy artefacts

The repo includes a small, optional production layout — not activated until Andrew chooses a
host and supplies real secrets outside Git:

| Path | Purpose |
| --- | --- |
| `deploy/Dockerfile` | Python 3.12 image; runs `deploy/entrypoint.sh` with `--proxy-headers` |
| `deploy/docker-compose.yml` | Example nginx + app on a fixed Docker subnet (`172.28.0.2` → `HV_TRUSTED_PROXIES`) |
| `deploy/nginx/*.example` | TLS reverse-proxy samples for Docker (`hv-swim.conf.example`) or systemd (`hv-swim-host.conf.example`) |
| `deploy/systemd/hv-swim.service.example` | Non-root `hvswim` unit; env from `/etc/hv-swim/hv-swim.env` |
| `deploy/.env.production.example` | Placeholder variable names only — copy to the server, never commit |

**Docker (staging rehearsal):** from the repository root, copy `deploy/.env.production.example`
to `deploy/.env`, replace every placeholder (HTTPS `HV_PUBLIC_URL`, 32+ character
`HV_SESSION_SECRET` and `HV_DATA_ENCRYPTION_KEY`, trusted proxy IP), add TLS files under
`deploy/certs/`, then:

`docker compose -f deploy/docker-compose.yml up --build`

Browse `https://127.0.0.1:8443` once DNS or `/etc/hosts` matches the configured name.
Management accounts require MFA before workspace access in production.

**systemd + nginx (bare metal or VM):** install the tree under `/opt/hv-swim`, create
`/var/lib/hv-swim` owned by `hvswim`, place secrets in `/etc/hv-swim/hv-swim.env` (mode
`600`), enable `deploy/systemd/hv-swim.service.example`, and point nginx at
`deploy/nginx/hv-swim-host.conf.example` with `HV_TRUSTED_PROXIES=127.0.0.1`.

Do not enable debug tooling, bind the API on a public interface without a proxy, or store
`.env` inside the image. Keep `HV_APP_ENV=production` on live hosts so demo accounts and
OpenAPI docs stay disabled.

SQLite is the implemented adapter. The project requires a separate production database
architecture decision before real child, family or payroll records are imported. Setting
DATABASE_URL does not implement PostgreSQL: unsupported settings fail closed. Database
adapter/migration implementation and backup/restore testing follow that decision.

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
