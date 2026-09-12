# HV Swim — sunlit rebuild

Local design release, 12 September 2026. Branch: `codex/sunlit-rebuild`.
Baseline: `beab5cb` from `origin/codex/platform-rebuild-20260906`.
Presentation: `5.13.0-ui19`; service-worker caches: `-20`.

## Result

The homepage now opens with a bright photographic composition, a clear enquiry action,
a three-step welcome, and an interactive pool beside program guidance. Public pages,
sign-in and portals share a navy, aqua, white and gold presentation with consistent
buttons, focus states, typography, surfaces and mobile spacing. The approved logo remains.

The Programs page includes an expandable first-lesson guide. The enquiry journey links
to it, preserves program recommendations, removes irrelevant guidance for general
questions, and shows a reference after successful submission. Private lesson prices
now consistently say to enquire across public program cards, dynamic timetable cards,
class preferences and the family class finder. This changes display only: it does not
alter approved invoice records or the database's class rates.

Family progress wording now describes skills and next steps without exposing internal
implementation language. Existing workforce, identity, reporting and integration
boundaries from the newer branch are retained. No live provider was activated.

The hero uses existing generated campaign imagery, identified as illustrative. It is
not a photograph of Laura, HV Swim customers or a confirmed venue. Existing provenance
and merchandise sample-approval requirements remain applicable.

## Working copy and local preview

The complete repository was moved, including its Git history and in-progress changes,
to `/Users/andrewhains/Developer/HV-Swim-School` after Andrew reiterated the sole-copy
rule. The Documents location contains no second repository.

Run `preview-local.command`, or:

```sh
cd ~/Developer/HV-Swim-School
.venv312/bin/python scripts/preview-local.py
```

Open http://127.0.0.1:8772/index.html. The launcher binds only to loopback, ignores
`.env`, removes inherited application/provider credentials, forces development mode,
and disables Xero sync. Synthetic data is in the Git-ignored `data/local-preview/`.
It is for demonstrations, not real child, health, customer or employment records.
The operating system may clear older temporary QA databases; this launcher does not
use them. The original production-capable launcher is retained for existing workflows.

## Verification performed during this rebuild

- Final Python suite: **152 passed, 1 skipped**. Two existing upstream deprecation
  warnings remain. Includes a new test that production data paths, credentials and
  sync settings cannot flow into the isolated preview environment.
- Static checker: **19 pages, 16 precached files, 11 scripts**, passed.
- Five Node regression scripts: scene input/motion, WebGL fallback, Melbourne dates,
  sign-in ordering and sign-out failure/success, passed. All asset/script JS syntax passed.
- HTTP smoke: **53 checks passed**. Security baseline: **20/20 passed**.
- Browser layout matrix: **60 public checks** (12 pages at 320/390/768/1024/1440),
  **46 management**, **26 staff**, and **24 family** checks. No page-width overflow,
  failed views or broken loaded public images in those checks.
- Direct browser interactions: mobile menu and Escape, pool-stage selection, motion
  pause, program matcher handoff, complete lesson enquiry, general enquiry validation
  and successful save, management receipt, each role's sign-in/out, staff start/break/
  end/finish, and break persistence across reload.
- Earlier synthetic enquiries were HV-ENQ-0001 and HV-ENQ-0002 in the isolated temporary
  QA database. The general enquiry appeared in the management inbox. A synthetic staff
  shift completed with 17 worked seconds; no payroll transmission occurred. The new
  persistent local preview starts with its own fresh demonstration records.
- Final source has no new frontend library dependency. Measured source sizes:
  homepage 32,893 bytes (8,746 gzip); experience stylesheet approximately 51 KB
  (12 KB gzip); experience JS 8,904 bytes; optional water JS 4,982 bytes; existing hero
  JPEG 323,280 bytes. These are asset sizes, not Lighthouse or real-device speed scores.

Screenshots are in `design/`. Automated checks do not certify accessibility, privacy,
production security or real-device performance. Physical-device/screen-reader testing,
production performance measurements and external-provider acceptance tests remain.

## Business decisions still needed

| Decision | Required answer / owner |
|---|---|
| Private tuition | Confirm the price, lesson length and whether the standard term rules apply. Owner: HV Swim management. |
| First lesson | Approve arrival timing, equipment/swim-nappy guidance, access instructions and the new guide. Owner: teaching team. |
| Real content | Supply approved venue/staff photography, image consents and current staff biography wording. |
| Term operations | Approve actual term dates, holidays, closures, class capacities, levels, rosters and enrolment procedures. |
| Bendigo East | Confirm HV Swim's program arrangements after the venue operator/opening is announced. Council's current page still says summer opening is unconfirmed. |
| Enquiry service | Assign inbox owners, response target and escalation process. No response deadline has been invented. |
| Merchandise | Approve products, rights, physical samples, sizes, prices, stock, shipping and returns before enabling checkout. |
| Policies | Obtain final privacy, retention, child-safeguarding, cancellations, photo-consent and employment-policy approval. |
| Launch | Choose hosting, domain/origin and production database architecture. Public deployment and live financial actions need Andrew's explicit approval. |

Council source checked 12 September 2026:
https://www.bendigo.vic.gov.au/things-do/pools-playgrounds-and-parks/pools/bendigo-east-swimming-pool

## Credentials and setup still required

Store actual credentials in a deployment secret store, never this document or Git.

| Service | Exact configuration and additional requirements |
|---|---|
| Production app | `HV_APP_ENV=production`, `HV_PUBLIC_URL`, separate strong `HV_SESSION_SECRET` and `HV_DATA_ENCRYPTION_KEY`, persistent private storage, HTTPS and host configuration; initial `HV_BOOTSTRAP_ADMIN_EMAIL` / `HV_BOOTSTRAP_ADMIN_PASSWORD`, removed after bootstrap; owner MFA enrolment. |
| Xero lessons | `XERO_CLIENT_ID`, `XERO_CLIENT_SECRET`, `XERO_REDIRECT_URI`; consent to the correct organisation; verified contact mappings; accountant-approved `XERO_LESSON_ACCOUNT_CODE`, `XERO_LESSON_TAX_TYPE`, `XERO_LINE_AMOUNT_TYPE`. Keep `XERO_SYNC_ENABLED=false` until explicitly authorised. |
| Xero payroll | Verified tenant, employee, payroll-calendar, pay-period and earnings mappings and appropriate OAuth scopes. Provider discovery and an operator reconciliation interface remain implementation work. Live payroll stays locked. |
| Shopify | `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_STOREFRONT_TOKEN`, approved API version and approved public catalogue; verify variants, stock, shipping, GST, refunds and checkout with test orders. |
| Google login | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`; approved consent screen and exact production callback. |
| Apple login | `APPLE_CLIENT_ID`, `APPLE_CLIENT_SECRET`, `APPLE_REDIRECT_URI`; verified Services ID/domain and team/key setup, private `.p8` key outside Git, secret rotation. |
| Account email | `HV_SMTP_HOST`, `HV_SMTP_PORT` (465), `HV_SMTP_USER`, `HV_SMTP_PASSWORD`, `HV_SMTP_FROM`; verify sender DNS and delivery. This covers account links, not general support notifications. |
| Weather | `OPEN_METEO_API_KEY` with commercial use rights; existing cache remains. |
| Optional sensor | `POOL_SENSOR_URL`, `POOL_SENSOR_TOKEN` and a verified reliable feed. Daily staff readings remain the default. |
| Optional Printify | `PRINTIFY_API_TOKEN`, `PRINTIFY_SHOP_ID`, approved Shopify connection and samples. |
| SMS / support email / push | Select providers and implement/test delivery, consent, opt-outs and receipts. Existing `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `SMS_PROVIDER`, `SMS_API_KEY`, `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY` placeholders alone do not activate these services. |

## Remaining engineering before production

SQLite is the implemented database. Merely setting a PostgreSQL URL is unsupported
and fails closed. A production database decision must be followed by adapter/migration
work, role/isolation tests, encrypted backup/restore rehearsal and approved data import.
Also outstanding: real provider acceptance tests, monitoring, independent security and
accessibility review, and the delivery adapters identified above. This release is a
verified local design and workflow rebuild, not a production launch.
