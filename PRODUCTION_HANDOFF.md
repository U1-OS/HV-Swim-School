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
- Decide whether a released class place should notify the next family automatically or remain a manager-approved action; the current build defaults to audited manager approval.
- Train managers to use Website content only for approved public wording and to verify every published change on mobile.
- HV Swim does not use clock-ins. The former clock endpoint is disabled and the platform
  uses published rosters plus reviewed timesheets with shift start/finish records. Do not
  re-enable background location or clock tracking without a new approved business,
  privacy and employment process.

Confirmed legal identity in this release: **HVS BENDIGO PTY LTD**, ABN
**46 687 937 962**, 76 Wood Street, California Gully VIC 3556; postal address PO Box
154, Wallan VIC 3756. Verify the ASIC/ABR extract and final public address presentation
with HV Swim before production deployment.

## 3. Existing Xero organisation

- Register a private Xero OAuth application and add its client ID, secret and callback URL.
- Map HV Swim staff to Xero employee and payroll-calendar IDs in the management workspace and confirm the earnings rate.
- Use the audited readiness preview to identify incomplete mappings. It never transmits payroll data.
- Import Xero pay-period boundaries and implement idempotent export tracking against the current AU Payroll API before any live transmission is enabled. `XERO_SYNC_ENABLED` is intentionally not sufficient to bypass this lock.
- Keep payroll approval in Xero; this website must never store Xero usernames or passwords.

## 4. Merchandise and Shopify

- Treat all 21 premium catalogue records as planned until each product passes the release gates below; a public concept card or saved-list entry is not inventory or an offer to supply.
- Use Shopify as the customer-facing source of truth for products, variants, stock, checkout, GST and refunds.
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

## 5. Notifications and app distribution

- Choose email, SMS and push providers and add sender-domain verification.
- Approve message templates, quiet hours, emergency escalation and opt-out handling.
- Active website and connected-app pages poll for urgent closure and changed-condition alerts and clear stale notices if the feed fails. This is not guaranteed off-device delivery and must not replace venue/emergency procedures.
- To reach a closed/backgrounded PWA or native app, implement and test Web Push plus APNs/FCM registration, consent, device-token lifecycle, provider credentials, delivery receipts and unsubscribe/removal. Browser notification permission by itself is not that service.
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
applicable usage rights. The public badge block is deliberately disabled by default, and
the Management → Staff compliance screen records the publication gate and official
requirement links. Do not scrape, redraw, recolour or use generic corporate logos as
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
