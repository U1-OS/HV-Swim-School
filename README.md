# HV Swim Bendigo V5.13.0 Premium Platform

Premium public website and connected operations platform for HV Swim Bendigo. The build combines a polished responsive front end with a FastAPI service, role-based accounts and a SQLite preview database. SQLite is not approved for the final production deployment that will store customer, child or payroll data.

## Preview on this Mac

The current UI18 workforce rebuild is documented in `PLATFORM_REBUILD.md` and
`WORKFORCE_OPERATIONS.md`. It adds exact server-timed shifts and breaks, scoped
management, invitations/recovery, optional authenticator MFA, approved CSV/XLSX
batches and a controlled Xero AU adapter. Live payroll remains locked.

The working copy lives at `/Users/u1/Developer/HV-Swim-School`, outside iCloud-synced
Desktop/Documents. Keep tested changes in the private `U1-OS/HV-Swim-School` GitHub repo;
do not upload `.env`, databases, certificates or customer records. The earlier Documents
location is retired, not a second working copy.

Double-click `start-hv-swim.command`, then use the Start Here page that opens in your default browser. On first launch, macOS may ask you to confirm opening the file. Keep the Terminal window open while previewing; close it to stop the local server.

The launcher requires Python 3.12 or newer and creates `.venv312` on first use, leaving
any older `.venv` intact. It starts the site at `http://127.0.0.1:8765` and opens
`START_HERE.html`. The GitHub quality workflow verifies Python 3.12.

See `INTERACTIVE_3D_REBUILD.md` for the 6 September 3D visual rebuild, browser checks,
motion controls and staff-date fixes. `PREMIUM_V2_UPGRADE_REPORT.md` covers the earlier
September review, validation evidence and
remaining launch gates. Development previews are explicitly labelled; sample accounts,
capacity and timetable data must not be represented as live business records.

## Main files

- `START_HERE.html` — preview hub
- `index.html` — public website
- `about.html` — Laura-led story, teaching principles and confidence-first approach
- `locations.html` — locations, weather and pool conditions
- `shop.html` — public merchandise studio with guided product plans, specifications and care guidance; cart/checkout stay hidden until an approved live Shopify catalogue is connected
- `enquire.html` — four-step lesson finder and database-backed enquiry form
- `programs.html` — premium program pathway, connected pricing, live places and guided lesson matcher
- `login.html` / `platform.html` — secure shared platform entry and role-based workspace
- `app.html` / `mobile-shell.html` — paused mobile source retained for a later phase; neither route is publicly served
- `MOBILE_APP_README.md` — paused mobile-phase notes retained for future planning
- `BRAND_GUIDE.md` — logo, colour, typography and merchandise usage guide
- `ASSOCIATION_BADGE_REQUIREMENTS.md` — evidence and authorised-artwork gate for third-party member/provider badges
- `IMAGE_ASSET_PROVENANCE.md` — exact V5.4/V5.6 image prompts, modes, masters and web outputs
- `prepare-mobile-app.command` / `capacitor.config.json` — paused Capacitor source retained outside the current website scope
- `backend/` — API, security, database and third-party integration boundaries
- `PRODUCTION_HANDOFF.md` — activation and deployment checklist

## Demonstration accounts

- Family: `parent@hvswim.demo` / `FamilyDemo!26`
- Staff: `staff@hvswim.demo` / `StaffDemo!26`
- Management: `admin@hvswim.demo` / `AdminDemo!26`

Demo credentials only work while `HV_APP_ENV=development`. Production mode disables them.

## Working in this build

- PBKDF2 password hashing, HttpOnly/SameSite=Strict sessions, one-way session-token storage, CSRF protection, rate limiting and role permissions
- Correlation IDs on every HTTP response, production-safe unhandled-error responses and
  route-aware request limits that allow verified staff certificate files up to 5 MB without
  weakening the normal 2 MB API boundary
- SQLite preview hardening with WAL, foreign-key enforcement, a bounded busy timeout and a
  protected Management system-health endpoint that verifies database integrity, ledger totals
  and integration-token encryption without exposing paths, credentials or customer records
- Versioned authenticated encryption for OAuth/integration tokens using the separate
  `HV_DATA_ENCRYPTION_KEY` in production, including automatic migration from the legacy
  session-key format at startup
- Real Google and Apple OpenID Connect foundation for family sign-up/sign-in, with
  PKCE/state/nonce protection, verified server-side identity tokens and provider tokens
  deliberately excluded from storage; staff and management identities remain invitation-only
- Family swimmers, editable emergency/allergy/medication/support profiles encrypted at rest, enquiry-first class preferences, existing lesson and waitlist visibility, cancellations and notices
- Automatic permanent family (`HVS-…`) and student (`HVS-S-…`) numbers, guaranteed again at lesson purchase and snapshotted into the Xero lesson-charge record so website, family, student and accounting records can be reconciled
- Management lesson-invoice ledger with grouped unbilled charges, local draft/approval controls, duplicate-charge protection, immutable event history and a deliberately gated Xero DRAFT-invoice handoff; families see only approved invoices and confirmed payment status
- Atomic invoice creation, approval and outbound claims plus strict Xero invoice-ID, DRAFT
  status, total/balance and customer-link reconciliation; unsafe or ambiguous provider
  responses move the record to manual review instead of changing the family ledger
- Family absence reporting against the active term calendar, with a visible two-credit
  allowance per swimmer and an explicit no-make-up/no-automatic-refund boundary
- Filtered family lesson finder with live capacity meters and enquiry links; families cannot self-enrol or join a waitlist from the portal
- Staff clock-on/clock-off with break recording, manual weekly/daily hour entry, permanent worker numbers, management approval, rosters, pool checks, achievements and private certificate-document tracking
- Role-protected incident/injury reporting linked to the family, student and worker numbers, with encrypted sensitive narratives, family-visible references and management follow-up status
- Date-based staff lesson registers with attendance, family-reported absence status,
  parent/guardian-on-site enforcement, photo-clearance snapshots and privacy-limited notes
- Source-labelled management dashboard with class utilisation, enquiry workload, hours pipeline and pool readiness
- Management enquiry-to-enrolment desk with today's run sheet, weekly capacity board and audited waitlist promotion after personal review
- Management term operations with draft/active/closed calendars, absence-credit ledger,
  term-aware “today” schedules and all-staff lesson-register oversight
- Responsive, searchable website navigation tailored to family, staff and management roles
- Location manager for public status, venue details, parking and accessibility information
- Safe CSV exports for enquiries, staff hours and the merchandise catalogue
- Staff-verified water temperatures, opening checklists and public condition updates
- Management metrics, roster/class creation, timesheet approvals, communications and audit trail
- Management website editor for the homepage announcement, lesson-enquiry status, hero message
  and primary call-to-action, plus server-enforced release gates for merchandise and
  third-party qualification/member marks
- Protected association-artwork register with PNG validation, SHA-256 integrity checks,
  evidence/expiry/usage-right tracking, audit history and automatic public fail-closed behaviour
- Management account and swimmer provisioning with a mandatory first password change
- Enquiry inbox with new, contacted, trial-booked and closed follow-up stages
- Asynchronous public support tickets with a returned reference and staff queue; the widget is not live chat or an emergency channel, and no external support email is sent yet
- Family-visible swimmer achievements with evidence, staff-private notes, audited issue/revocation and eight printable certificate styles that are not qualifications or accreditation
- Family-controlled in-portal lesson reminders plus urgent pool-closure and changed-condition alerts that poll while a website page is open; email/SMS and off-device push are not active
- Management merchandise workspace for the premium 24-product plan, with sample tracking, supplier routes, costs, projected margin and quantified launch readiness
- Guided First Splash, Lesson Day and Family Club product plans that remain non-orderable until the approved Shopify catalogue is connected, with progressive product loading for faster mobile browsing
- Role-protected staff uniform catalogue available only inside the Staff and Management workspaces; staff products are excluded from the public product API
- Product material, care and personalisation guidance with explicit sample-approval boundaries
- Local catalogue price/status controls before products are approved for Shopify
- Cached Bendigo outdoor weather through the server-side weather service; production requires a commercial Open-Meteo key
- Premium “Today at HV Swim” homepage view combining local weather, staff-verified pool conditions, seasonal venue status and the next connected class place
- Privacy-first optional Facebook timeline with a direct-page fallback and a Meta connection only after visitor consent
- Venue-specific Acknowledgement of Country and source-linked public SWIM, AUSTSWIM and Autism Swim directory records
- Distinct, locally optimised program, enquiry and Laura-led approach campaign imagery
- Enquiry preference recovery that deliberately excludes names, contact details and free-text notes from browser storage
- Role-specific family and staff next-action hubs plus a management attention queue built from existing API data
- Cached Shopify storefront/cart and Printify catalogue boundaries
- Xero OAuth connection, staff mapping and an audited payroll-readiness preview; the durable timesheet adapter is implemented and locally tested, while outbound payroll stays locked pending provider-verified resources/pay periods and operator reconciliation
- Explicit payment routing: lesson/term charges and approved absence-credit adjustments
  belong to the reviewed Xero invoicing workflow; approved merchandise belongs to Shopify
  Checkout, with staff uniforms kept inside protected staff/management views. Neither route
  fabricates payments when credentials or launch gates are incomplete.
- VistaPrint/manual and specialist-swim supplier plans for products unsuitable for generic POD
- Mobile-first website interfaces and an offline public fallback
- Refined transparent HV Swim logo system, simplified digital mark, refreshed social image,
  refreshed website icon family and locally hosted Manrope typography
- Cohesive premium visual system across the public site, sign-in, family, staff and
  management experiences with improved role-aware navigation and responsive density

## External activation boundaries

Google family access requires an HV Swim-owned Google Cloud OAuth web client. Apple/iCloud
family access requires an Apple Developer Services ID and generated, rotated client secret. Until
those values are present, both buttons remain visible but disabled as “Setup required”; the
preview never fabricates a provider login. Connecting the existing Xero organisation and
enabling the reviewed DRAFT-invoice handoff requires an HV Swim-owned OAuth app, verified
family contact mappings, lesson account code, tax type, line-amount type and explicit outbound
switch. Shopify, Printify, VistaPrint ordering, commercial
weather, email, SMS, push, pool sensors, hosting and domain
likewise require credentials or accounts owned by HV Swim. Those values belong in a private
`.env` file created from `.env.example`; secrets must never be placed in HTML or committed to
source control. Credentials do not activate email, SMS or push by themselves—the provider
adapters and consent workflows are still explicit launch work. The optional Meta Page Plugin
is configured but must be tested on the approved production domain.

The website never presents directory membership as instructor accreditation. Management can upload only the current member/provider PNG issued through HV Swim's own organisation account and must record its reference, expiry and usage rights. Generic or scraped organisation logos are not included. The entire public section stays hidden until all three records pass and management separately enables it under Website content. Follow `ASSOCIATION_BADGE_REQUIREMENTS.md` and `PRODUCTION_HANDOFF.md` before activation.

The 24 merchandise records are a production plan, not available stock. The public store separates premium swimwear, embroidered towels and hooded ponchos, goggles/equipment, named drinkware and POD family wear while showing each proposed production route. Staff uniforms are excluded from the public API and appear only in role-protected Staff and Management workspaces. Every product must pass artwork-rights, specification, landed-cost, physical-sample, care/returns and end-to-end Shopify release gates. Supplier and blank-brand names identify possible sourcing routes only; they do not claim a partnership, endorsement, licence or authorised-reseller relationship with HV Swim.

Support messages currently enter the protected management queue and return a reference; external email delivery is not implemented. Lesson reminders and urgent notices refresh inside active website sessions. Reaching a closed browser or sending email/SMS still requires a consented production provider and a tested delivery adapter.

The direct management entry is `http://127.0.0.1:8765/login.html?role=admin`. In development, the page can load the Management demo account from the local server. Production never exposes demo credentials. After signing in, use **Term operations** for approved calendar dates and credit oversight, **Lesson registers** for attendance review, **Website content** for approved homepage fields, **Enquiry inbox** for family follow-up and **Merchandise** for the launch catalogue.

Pool water temperature is not inferred from outdoor weather. It remains a daily staff-verified reading unless the venue supplies a compatible sensor feed.

## Data and reset

Local preview data is stored in `data/hv_swim.db`. The database is intentionally excluded from the delivery ZIP so every fresh copy starts with clean seeded demonstration data. Production must use managed PostgreSQL, encrypted backups, a strong `HV_SESSION_SECRET`, a separate strong `HV_DATA_ENCRYPTION_KEY` and environment-specific secrets.

## Quality checks

Use Python 3.12+ and Node.js 22+, then run:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -q
node scripts/check-site.mjs
```

The same backend and static-site checks run automatically for pushes and pull requests in the private GitHub repository. The native-app phase is paused and is not part of the current release gate.

## Generated visual assets

The homepage hero, page-specific program/enquiry/about imagery, merchandise campaign visuals and logo refinement were created
with the built-in OpenAI image-generation tool using supplied HV Swim artwork as the brand
reference. The transparent logo and icon files are approved digital/sample proofs only;
`BRAND_GUIDE.md` records the required manual vector, colour and physical-sampling work before
bulk merchandise production. The new photographs are clearly generic campaign imagery and do
not depict Laura, HV Swim staff or customers. Product campaign images remain concepts until
final products and manufacturer specifications are approved.
