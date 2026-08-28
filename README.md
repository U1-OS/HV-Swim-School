# HV Swim Bendigo V5.4 Premium Platform

Premium public website, installable Progressive Web App and connected operations platform for HV Swim Bendigo. The build combines a polished responsive front end with a FastAPI service, role-based accounts and a SQLite preview database. SQLite is not approved for the final production deployment that will store customer, child or payroll data.

## Preview on this Mac

Double-click `start-hv-swim.command`, then use the Start Here page that opens in your default browser. On first launch, macOS may ask you to confirm opening the file. Keep the Terminal window open while previewing; close it to stop the local server.

The launcher creates its own Python environment and installs the pinned dependencies on first use. It starts the site at `http://127.0.0.1:8765` and opens `START_HERE.html`. Production uses Python 3.12 or newer; the GitHub quality workflow verifies that baseline.

## Main files

- `START_HERE.html` — preview hub
- `index.html` — public website
- `about.html` — Laura-led story, teaching principles and confidence-first approach
- `locations.html` — locations, weather and pool conditions
- `shop.html` — public merchandise studio with guided kits, product specifications, care guidance, variants and a persistent preview cart
- `enquire.html` — four-step lesson finder and database-backed enquiry form
- `programs.html` — premium program pathway, connected pricing, live places and guided lesson matcher
- `login.html` / `platform.html` — secure shared platform entry and role-based workspace
- `app.html` — installable app experience
- `mobile-shell.html` — native iOS/Android connection launch experience
- `MOBILE_APP_README.md` — Mac, Xcode, Android Studio and store-build guide
- `BRAND_GUIDE.md` — logo, colour, typography and merchandise usage guide
- `IMAGE_ASSET_PROVENANCE.md` — exact V5.4 image prompts, modes, masters and web outputs
- `prepare-mobile-app.command` — creates and synchronises the Capacitor iOS/Android projects
- `capacitor.config.json` / `package.json` — Capacitor 8 native project foundation
- `backend/` — API, security, database and third-party integration boundaries
- `PRODUCTION_HANDOFF.md` — activation and deployment checklist

## Demonstration accounts

- Family: `parent@hvswim.demo` / `FamilyDemo!26`
- Staff: `staff@hvswim.demo` / `StaffDemo!26`
- Management: `admin@hvswim.demo` / `AdminDemo!26`

Demo credentials only work while `HV_APP_ENV=development`. Production mode disables them.

## Working in this build

- PBKDF2 password hashing, HttpOnly sessions, CSRF protection, rate limiting and role permissions
- Family swimmers, class availability, bookings, cancellations, waitlists and notices
- Filtered family class finder with live capacity meters and visible waitlist positions
- Staff rosters, clock-in/out, pool-deck location, timesheets and qualification tracking
- Source-labelled management dashboard with class utilisation, enquiry workload, hours pipeline and pool readiness
- Management enrolment desk with today's run sheet, weekly capacity board and audited waitlist promotion
- App-style mobile tab navigation tailored to family, staff and management roles
- Native-ready Capacitor 8 launch shell for iOS and Android
- Safe-area layouts, offline public-data cache and honest connection status
- 1024px store icon source, store-listing draft and Apple/Google release gates
- Location manager for public status, venue details, parking and accessibility information
- Safe CSV exports for enquiries, staff hours and the merchandise catalogue
- Staff-verified water temperatures, opening checklists and public condition updates
- Management metrics, roster/class creation, timesheet approvals, communications and audit trail
- Management website editor for the homepage announcement, enrolment status, hero message and primary call-to-action
- Management account and swimmer provisioning with a mandatory first password change
- Enquiry inbox with new, contacted, trial-booked and closed follow-up stages
- Management merchandise workspace with sample tracking, supplier routes, costs, projected margin and quantified launch readiness
- Guided First Splash, Lesson Day and Pool Deck uniform kits that add coordinated products to the persistent preview cart
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
- Xero OAuth connection, staff mapping and an audited payroll-readiness preview; outbound payroll transmission remains locked until real pay periods and idempotent export tracking are implemented
- VistaPrint/manual and specialist-swim supplier plans for products unsuitable for generic POD
- PWA manifest, app icons, offline public shell and mobile-first interfaces
- Refined transparent HV Swim logo system, simplified digital mark, refreshed social image,
  new native/PWA icon family and locally hosted Manrope typography
- Cohesive premium visual system across the public site, sign-in, family, staff and
  management experiences with improved role-aware navigation and responsive density

## External activation boundaries

Connecting the existing Xero organisation requires an HV Swim-owned OAuth app and mappings. Shopify, Printify, VistaPrint ordering, commercial weather, email, SMS, push, pool sensors, hosting, domain and native app-store distribution likewise require credentials or accounts owned by HV Swim. Those values belong in a private `.env` file created from `.env.example`; secrets must never be placed in HTML or committed to source control. Credentials do not activate email, SMS or push by themselves—the provider adapters and consent workflows are still explicit launch work. The optional Meta Page Plugin is configured but must be tested on the approved production domain.

The website links to public industry directory records without presenting them as instructor accreditation. Use only current member/provider badge files issued through HV Swim's own organisation accounts. Generic or scraped organisation logos are not included. See `PRODUCTION_HANDOFF.md` for the directory-record differences that HV Swim must reconcile before launch.

The direct management entry is `http://127.0.0.1:8765/login.html?role=admin`. In development, the page can load the Management demo account from the local server. Production never exposes demo credentials. After signing in, use **Website content** for approved homepage fields, **Enquiry inbox** for family follow-up and **Merchandise** for the launch catalogue.

Pool water temperature is not inferred from outdoor weather. It remains a daily staff-verified reading unless the venue supplies a compatible sensor feed.

## Data and reset

Local preview data is stored in `data/hv_swim.db`. The database is intentionally excluded from the delivery ZIP so every fresh copy starts with clean seeded demonstration data. Production should use managed PostgreSQL, encrypted backups and environment-specific secrets.

## Quality checks

Use Python 3.12+ and Node.js 22+, then run:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -q
node scripts/check-site.mjs
node scripts/build-mobile-web.mjs
```

The same backend, static-site and mobile-shell checks run automatically for pushes and pull requests in the private GitHub repository.

## Generated visual assets

The homepage hero, page-specific program/enquiry/about imagery, merchandise campaign visuals and logo refinement were created
with the built-in OpenAI image-generation tool using supplied HV Swim artwork as the brand
reference. The transparent logo and icon files are approved digital/sample proofs only;
`BRAND_GUIDE.md` records the required manual vector, colour and physical-sampling work before
bulk merchandise production. The new photographs are clearly generic campaign imagery and do
not depict Laura, HV Swim staff or customers. Product campaign images remain concepts until
final products and manufacturer specifications are approved.
