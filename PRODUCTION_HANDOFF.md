# HV Swim Bendigo production handoff

This build is a production foundation, not a substitute for the final deployment process. The public experience and core workflows are implemented; the following activation work requires HV Swim-owned accounts, decisions or real operating data.

## 1. Hosting and security

- Deploy the FastAPI service behind HTTPS on an Australian-region host.
- Use Python 3.12 or newer and keep the GitHub quality workflow green.
- Replace SQLite with managed PostgreSQL before real customer use.
- Set a long random `HV_SESSION_SECRET` and `HV_APP_ENV=production`.
- On the first start of an empty production database only, set
  `HV_BOOTSTRAP_ADMIN_EMAIL` and a unique `HV_BOOTSTRAP_ADMIN_PASSWORD` (12+ characters),
  then remove both values after the management account has been created.
- Configure the real public origin in `HV_PUBLIC_URL` and restrict allowed hosts.
- Add automated encrypted backups, uptime checks, error monitoring and a restore drill.
- Run an independent penetration test before collecting customer or staff information.

## 2. Accounts, privacy and safeguarding

- Import only approved customer, swimmer, staff and class data.
- Reconcile the command-centre metric definitions against the production database and assign an owner for each operational KPI.
- Keep source mode and refresh time visible; never label seeded preview records as live business results.
- Store exported CSV files only in an approved business location and delete local copies under the agreed retention policy.
- Use the management Accounts workspace to provision families, staff and swimmers; every new account must replace its temporary password at first sign-in.
- Implement verified password recovery, account deletion, active-session management and manager MFA before public/app-store launch.
- Have an Australian privacy professional review consent, retention and child-safeguarding language.
- Add the approved privacy policy, terms, cancellation policy and photo/media consent wording.
- Confirm accessibility against WCAG 2.2 AA with keyboard and assistive-technology testing.
- Set enquiry ownership, response targets and deletion/retention rules before the public form goes live.
- Confirm enrolment authority, waitlist priority rules, payment collection and signed-terms requirements before managers promote real families into classes.
- Decide whether a released class place should notify the next family automatically or remain a manager-approved action; the current build defaults to audited manager approval.
- Train managers to use Website content only for approved public wording and to verify every published change on mobile.

## 3. Existing Xero organisation

- Register a private Xero OAuth application and add its client ID, secret and callback URL.
- Map HV Swim staff to Xero employee and payroll-calendar IDs in the management workspace and confirm the earnings rate.
- Use the audited readiness preview to identify incomplete mappings. It never transmits payroll data.
- Import Xero pay-period boundaries and implement idempotent export tracking against the current AU Payroll API before any live transmission is enabled. `XERO_SYNC_ENABLED` is intentionally not sufficient to bypass this lock.
- Keep payroll approval in Xero; this website must never store Xero usernames or passwords.

## 4. Merchandise and Shopify

- Use Shopify as the customer-facing source of truth for products, variants, stock, checkout, GST and refunds.
- Connect Printify to Shopify for suitable on-demand garments and accessories. Keep Printify order approval manual during sampling and launch.
- Use VistaPrint/manual ordering for selected embroidered uniforms, bottles and bulk promotional products where it wins on quality or price.
- Use a specialist swim supplier for chlorine-resistant swimwear, silicone caps, goggles and any item whose safety or durability cannot be assured by generic POD.
- Approve the product range, suppliers, sizing, pricing, returns, minimum order quantities and fulfilment method.
- Request one physical sample of every product/variant family; test logo colour, wash/chlorine resistance, comfort and packaging before publishing.
- Replace concept images with approved product photography or supplier-authorised mock-ups.
- Create the Shopify catalogue and Storefront access token, then add the domain and token to `.env`.
- Add the Printify API token and shop ID to `.env` only if the read-only admin catalogue sync is wanted.
- Test stock, variants, shipping, GST, checkout, refunds and mobile purchases end-to-end.
- Follow `MERCH_PRODUCTION_PLAN.md` for the initial supplier map and release gates.

## 5. Notifications and app distribution

- Choose email, SMS and push providers and add sender-domain verification.
- Approve message templates, quiet hours, emergency escalation and opt-out handling.
- Use the existing PWA immediately; its offline mode never queues sensitive changes without confirmation.
- Confirm the production HTTPS app origin and permanent bundle ID, then run `prepare-mobile-app.command` to create and synchronise the Capacitor iOS/Android projects.
- Follow `MOBILE_APP_README.md` and `mobile/STORE_HANDOFF.md` for Xcode 26, Android API 36, signing, beta testing, privacy disclosures and store assets.
- Treat native push notification setup as a separate consented production integration; the included web and native shells do not pretend that provider credentials are active.

## 6. Pool temperatures and conditions

- Keep daily staff verification as the operational source of truth.
- If a venue exposes a sensor feed, add its endpoint and token only after confirming reliability, units and outage behaviour.
- Do not display a stale sensor or manual reading as current; the build marks readings older than 24 hours for review.

## 7. Weather and lesson calendar

- Add an Open-Meteo commercial customer API key for production. The free endpoint is used only for local development.
- Keep the server-side cache enabled so each visitor does not create a new provider request.
- Add approved term dates, public holidays, venue closures and one-off lesson exceptions before treating recurring “today” class suggestions as an authoritative operating run sheet.

## Launch sign-off

Complete real-data migration, browser/device QA, payment testing, payroll dry run, backup restore, legal review, accessibility review and staff training before public production launch.
