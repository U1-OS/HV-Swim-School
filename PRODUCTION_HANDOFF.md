# HV Swim Bendigo production handoff

This build is a production foundation, not a substitute for the final deployment process. The public experience and core workflows are implemented; the following activation work requires HV Swim-owned accounts, decisions or real operating data.

## 1. Hosting and security

- Deploy the FastAPI service behind HTTPS on an Australian-region host.
- Use Python 3.12 or newer and keep the GitHub quality workflow green.
- Replace SQLite with managed PostgreSQL before real customer use.
- Set a long random `HV_SESSION_SECRET`, a separate long random
  `HV_DATA_ENCRYPTION_KEY` and `HV_APP_ENV=production`. Keep both keys in the hosting
  secret store and outside the database, backups and repository.
- On the first start of an empty production database only, set
  `HV_BOOTSTRAP_ADMIN_EMAIL` and a unique `HV_BOOTSTRAP_ADMIN_PASSWORD` (12+ characters),
  then remove both values after the management account has been created.
- Configure the real public origin in `HV_PUBLIC_URL` and restrict allowed hosts.
- Add automated encrypted backups, uptime checks, error monitoring and a restore drill.
- Monitor the public `/api/health` route for uptime and use the authenticated
  `/api/admin/system-health` route after deployment, database migration and every restore.
  It reports integrity, foreign-key, finance-ledger and encryption-format readiness without
  exposing storage paths or secrets. Forward the `X-Request-ID` response header into the
  production log/error-monitoring context for support correlation.
- The SQLite preview now uses WAL and bounded lock waits, but that does not change the
  requirement to move real customer, swimmer, billing and payroll records to managed
  PostgreSQL before production.
- Run an independent penetration test before collecting customer or staff information.
  The included automated and local security audits are a baseline, not an “unhackable” claim.

## 2. Accounts, privacy and safeguarding

- Create an HV Swim-owned Google Cloud OAuth web client and configure the production HTTPS
  callback in `GOOGLE_REDIRECT_URI`. Complete the Google consent-screen/domain verification.
- Create an Apple Developer Services ID for the website, associate and verify the production
  domain/return URL, generate a time-limited client secret from the Apple team/key IDs and
  private `.p8` key, then configure `APPLE_CLIENT_ID` and `APPLE_CLIENT_SECRET`. Keep the
  `.p8` key outside this project and schedule secret rotation before it expires.
- Test Google and Apple with new families, returning families, Apple private relay addresses,
  cancellation, revoked consent and account deletion. Buttons deliberately show “Setup
  required” until their complete server-side configuration is present.
- Confirm the operating rule that provider sign-up creates customer/family accounts only.
  Staff and management identities remain invitation-controlled and fail closed if their work
  email is presented by Google or Apple.
- Import only approved customer, swimmer, staff and class data.
- Reconcile the command-centre metric definitions against the production database and assign an owner for each operational KPI.
- Keep source mode and refresh time visible; never label seeded preview records as live business results.
- Store exported CSV files only in an approved business location and delete local copies under the agreed retention policy.
- Use the management Accounts workspace to provision families, staff and swimmers; every new account must replace its temporary password at first sign-in.
- Implement verified password recovery, account deletion, active-session management and manager MFA before public/app-store launch.
- Have an Australian privacy professional review consent, retention and child-safeguarding language.
- Have the included privacy, terms, cancellation and photo/media consent wording reviewed
  by an Australian legal professional before launch. The build now records the confirmed
  operating rules: $22.50 per lesson billed by term and due on enrolment; two absence
  credits per term; no make-up lessons; no mid-term cancellation refund subject to the
  Australian Consumer Law; a parent/guardian onsite except for Stroke Development; and no
  photos without class/swimmer clearance.
- Confirm accessibility against WCAG 2.2 AA with keyboard and assistive-technology testing.
- Paul and Laura Smith are the complaint/question contacts at
  `bendigo@hvswimschool.com`. Set an internal response target and escalation procedure
  before the public form goes live. Public enquiries are automatically deleted after six
  months; verify that production backups and exports follow the same approved schedule.
- Staff records are retained to the end of the relevant financial year unless law,
  safeguarding or an active dispute requires longer. Confirm the exact deletion job with
  legal/payroll advisers before automating deletion in production.
- Assign the asynchronous support-ticket queue to a staffed role, publish a response target and retention period, and train staff that it is not monitored as live chat or an emergency service. The current build creates an internal queue item and reference only; it does not send an external support email.
- Approve who may issue or revoke swimmer achievements. Families see the achievement and evidence note, while the staff note remains private; issue and revocation events are audited. Treat printable HTML certificates as HV Swim progress records, never as qualifications, licences or industry accreditation.
- Confirm enrolment authority, waitlist priority rules, payment collection and signed-terms requirements before managers promote real families into classes.
- Every family and swimmer receives a permanent HV number when the account/record is created. The lesson-purchase workflow rechecks and backfills both identifiers before creating the Xero charge record. Preserve those identifiers during migration, map the family number to the Xero contact and Shopify customer metafield, and never recycle a retired number.
- Decide whether a released class place should notify the next family automatically or remain a manager-approved action; the current build defaults to audited manager approval.
- Train managers to use Website content only for approved public wording and to verify every published change on mobile.
- HV Swim now requires staff clock-on, break and clock-off records as well as optional
  manual weekly/daily hour entry. Completed entries remain subject to management approval
  before the Xero payroll workflow. The clock records timestamps and a selected workplace;
  it does not request GPS, background location or continuous device tracking. Confirm the
  employment/privacy notice and break-rounding policy before production use.
- Configure an incident-retention, correction and escalation procedure before real use. Sensitive incident narratives are encrypted and routed by family, student and worker number; authorised management still needs an approved safeguarding workflow, breach-response plan and restricted backup/export process.

Confirmed legal identity in this release: **HVS BENDIGO PTY LTD**, ABN
**46 687 937 962**, 76 Wood Street, California Gully VIC 3556; postal address PO Box
154, Wallan VIC 3756. Verify the ASIC/ABR extract and final public address presentation
with HV Swim before production deployment.

## 3. Existing Xero organisation

- Register a private Xero OAuth application and add its client ID, secret and callback URL.
- Use Xero as the financial route for lesson enrolments, term invoices and any approved
  absence-credit adjustment. Shopify is reserved for merchandise and uniforms; do not mix
  lesson fees into the Shopify cart.
- The current build implements reviewed local invoice drafting, management approval,
  idempotent Xero DRAFT-invoice creation and status/payment reconciliation. Before enabling
  transmission, verify the contact mapping, lesson account code, tax type and line-amount type
  with the business accountant, then test the complete workflow in the intended Xero
  organisation. Credit-note creation remains unimplemented and must not be inferred from the
  absence-credit record.
- Invoice creation, approval and the outbound claim are transactionally serialized. Xero
  responses must confirm the requested invoice ID, draft status and a balance that matches
  the approved local total; invalid totals, IDs or customer payment links remain in manual
  review. Do not bypass that state in the database—compare the record in Xero and the audit
  trail first.
- Use the permanent HV family number as the external contact reference and include the relevant
  student number on the lesson invoice line. The platform snapshots both values and can create
  a draft against a verified, manually mapped Xero Contact ID; it does not create or merge Xero
  contacts automatically.
- Map HV Swim staff to Xero employee and payroll-calendar IDs in the management workspace and confirm the earnings rate.
- Use the audited readiness preview to identify incomplete mappings. It never transmits payroll data.
- Import Xero pay-period boundaries and implement idempotent export tracking against the current AU Payroll API before any live transmission is enabled. `XERO_SYNC_ENABLED` is intentionally not sufficient to bypass this lock.
- Keep payroll approval in Xero; this website must never store Xero usernames or passwords.

## 4. Merchandise and Shopify

- Treat all 24 premium catalogue records as planned until each product passes the release gates below; a public concept card or saved-list entry is not inventory or an offer to supply.
- Use Shopify as the customer-facing source of truth for products, variants, stock, checkout, GST and refunds.
- Store the permanent HV family number in an approved Shopify customer metafield when the live customer sync is implemented. Shopify customer IDs must remain mapping identifiers, not the authoritative HV family number.
- Keep public Shopify Checkout scoped to approved family merchandise. Staff uniforms must
  remain in the role-protected Staff and Management workspaces and must not be published in
  public Shopify collections or the public product API. Lesson and term payments stay in the
  Xero invoicing route.
- Connect Printify to Shopify for suitable on-demand garments and accessories. Keep Printify order approval manual during sampling and launch.
- Use VistaPrint/manual ordering for selected embroidered uniforms, bottles and bulk promotional products where it wins on quality or price.
- Use a specialist swim supplier for chlorine-resistant swimwear, silicone caps, goggles and any item whose safety or durability cannot be assured by generic POD.
- Approve the product range, suppliers, sizing, pricing, returns, minimum order quantities and fulfilment method.
- Request one physical sample of every product/variant family; test logo colour, wash/chlorine resistance, comfort and packaging before publishing.
- Replace concept images with approved product photography or supplier-authorised mock-ups.
- Confirm that every named blank brand is sourced and decorated through an authorised reseller. Supplier and brand names are candidates only and must not be presented as HV Swim partners, sponsors, endorsers or licensees without written authority.
- Create the Shopify catalogue and Storefront access token, then add the domain and token to `.env`.
- Add the Printify API token and shop ID to `.env` only if the read-only admin catalogue sync is wanted.
- Test stock, variants, shipping, GST, checkout, refunds and mobile purchases end-to-end.
- Follow `MERCH_PRODUCTION_PLAN.md` for the initial supplier map and release gates.

## 5. Notifications and website delivery

- Choose email, SMS and push providers and add sender-domain verification.
- Approve message templates, quiet hours, emergency escalation and opt-out handling.
- Active website pages poll for urgent closure and changed-condition alerts and clear stale
  notices if the feed fails. Signed-in family accounts can choose a 12, 24 or 48-hour
  in-portal lesson reminder. These are not guaranteed off-device delivery and must not
  replace venue or emergency procedures.
- Implement and test the email/SMS adapters, verified sender, consent, quiet hours,
  idempotency, delivery receipts and opt-out handling before enabling external reminders.
- The mobile-app phase is paused. `app.html` and `mobile-shell.html` are retained as source
  but are not publicly served, linked or included in the website sitemap. Do not start
  store submission or APNs/FCM work until HV Swim approves a new mobile scope.

## 6. Pool temperatures and conditions

- Keep daily staff verification as the operational source of truth.
- If a venue exposes a sensor feed, add its endpoint and token only after confirming reliability, units and outage behaviour.
- Do not display a stale sensor or manual reading as current; the build marks readings older than 24 hours for review.

## 7. Weather and lesson calendar

- Add an Open-Meteo commercial customer API key for production. The free endpoint is used only for local development.
- Keep the server-side cache enabled so each visitor does not create a new provider request.
- Enter and activate approved term dates under Management → Term operations. The platform
  now suppresses “today” classes outside the active term and uses those dates for family
  absence credits and staff lesson registers. The bundled development term is visibly
  labelled preview-only and is never seeded in production.
- Add approved public holidays, venue closures and one-off lesson exceptions before treating
  the recurring in-term “today” class suggestions as a fully authoritative operating run sheet.

## 8. Associations, public directories and third-party marks

The public website does not claim school or instructor accreditation. Verification reviewed
30 August 2026 found the following public records and official publication rules:

- SWIM Coaches & Teachers Australia publishes an HV Swim Bendigo swim-school finder record.
- AUSTSWIM describes its Swim School Network as membership and says a digital badge is
  issued after membership confirmation. Confirm HV Swim's current membership and use only
  the issued badge file.
- SWIM Schools Australia says current members receive the right to display its member logo.
  Confirm current membership before enabling the mark.
- Autism Swim says approved aquatic providers receive approved logos/marketing resources
  and that certification requires ongoing training and renewal. Confirm HV Swim's active
  certification and use only the current provider artwork.

Before displaying organisation logos or badges, complete
`ASSOCIATION_BADGE_REQUIREMENTS.md`: obtain the exact current member/provider artwork
issued through HV Swim's own account, record the renewal/expiry evidence and confirm the
applicable usage rights. Management → Staff compliance now provides the protected evidence
and PNG-artwork register, validates file integrity and records the reviewer. Management →
Website content is the separate final release control and stays server-locked until all
three records pass. Expiry or file-integrity failure automatically hides the complete
public block. Persist and back up the private runtime artwork directory in production, or
move it to private object storage without weakening the gate. Do not scrape, redraw, recolour or use generic corporate logos as
substitute membership badges. Do not publish personal AUSTSWIM, SWIM or Autism Swim
qualifications for Laura or another instructor without a current certificate/licence type,
issuing body and expiry date.

HV Swim must nominate the canonical public business details, then correct every external directory. Current records disagree with this repository on `76` versus `76B` Wood Street, postcode `3550` versus `3556`, phone `0413 462 112` versus `0458 733 323`, Hotmail versus `bendigo@hvswimschool.com`, and `31` versus `33` Lansell Street. The Autism Swim page also still names Andrea; Andrea has been removed from this repository and that external record needs an owner-requested update.

## 9. Facebook and Acknowledgement of Country

- The homepage Meta Page Plugin remains opt-in and no Facebook request is made until the visitor chooses to load it. The content-security policy permits only `https://www.facebook.com` as an external frame source.
- On the approved production domain, test the optional timeline while signed out on desktop and mobile, with common privacy/content blockers enabled, and confirm the direct Facebook link remains a usable fallback. Meta controls availability and presentation; do not treat the embedded feed as an owned content archive.
- Have the Meta disclosure in `privacy.html` reviewed with the rest of the privacy policy before launch.
- Confirm the Country for each operating venue and have the venue-specific Acknowledgement of Country reviewed by the appropriate local authority or cultural adviser. The accompanying HV-designed sun/water mark is an abstract local graphic, not Indigenous artwork or an approved cultural symbol.

## Launch sign-off

Complete real-data migration, browser/device QA, payment testing, payroll dry run, backup restore, legal review, accessibility review and staff training before public production launch.
