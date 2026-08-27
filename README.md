# HV Swim Bendigo V5.0 Public Launch Experience

Premium public website, installable Progressive Web App and connected operations platform for HV Swim Bendigo. The build combines a polished responsive front end with a local FastAPI service, role-based accounts and SQLite data persistence.

## Preview on this Mac

Double-click `start-hv-swim.command`, then use the Start Here page that opens in your default browser. On first launch, macOS may ask you to confirm opening the file. Keep the Terminal window open while previewing; close it to stop the local server.

The launcher creates its own Python environment and installs the pinned dependencies on first use. It starts the site at `http://127.0.0.1:8765` and opens `START_HERE.html`.

## Main files

- `START_HERE.html` — preview hub
- `index.html` — public website
- `about.html` — Laura-led story, teaching principles and confidence-first approach
- `locations.html` — locations, weather and pool conditions
- `shop.html` — public merchandise and uniform catalogue
- `enquire.html` — lesson finder and database-backed enquiry form
- `programs.html` — premium program pathway, connected pricing, live places and guided lesson matcher
- `shop.html` — premium nine-product storefront with search, variants, persistent preview cart and Shopify/POD launch boundaries
- `enquire.html` — four-step enrolment concierge with program matching, connected class preferences, structured management handoff and confirmation references
- `login.html` / `platform.html` — secure shared platform entry and role-based workspace
- `app.html` — installable app experience
- `mobile-shell.html` — native iOS/Android connection launch experience
- `MOBILE_APP_README.md` — Mac, Xcode, Android Studio and store-build guide
- `prepare-mobile-app.command` — creates and synchronises the Capacitor iOS/Android projects
- `capacitor.config.json` / `package.json` — Capacitor 8 native project foundation
- `backend/` — API, security, database and third-party integration boundaries
- `PRODUCTION_HANDOFF.md` — activation and deployment checklist

## Demonstration accounts

- Family: `parent@hvswim.demo` / `FamilyDemo!26`
- Staff: `staff@hvswim.demo` / `StaffDemo!26`
- Management: `admin@hvswim.demo` / `AdminDemo!26`

Demo credentials only work while `HV_ENVIRONMENT=development`. Production mode disables them.

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
- Enquiry inbox with new, contacted, trial-booked and closed follow-up stages
- Management merchandise workspace with supplier routing and launch gates
- Local catalogue price/status controls before products are approved for Shopify
- Live Bendigo outdoor weather through the server-side weather service
- Premium “Today at HV Swim” homepage view combining local weather, staff-verified pool conditions, seasonal venue status and the next connected class place
- Shopify storefront/cart, Printify catalogue and Xero OAuth/payroll integration boundaries
- VistaPrint/manual and specialist-swim supplier plans for products unsuitable for generic POD
- PWA manifest, app icons, offline public shell and mobile-first interfaces

## External activation boundaries

Real Xero, Shopify, Printify, VistaPrint ordering, email, SMS, push, pool sensors, hosting, domain and native app-store distribution require credentials or accounts owned by HV Swim. Those values belong in a private `.env` file created from `.env.example`; secrets must never be placed in HTML or committed to source control.

The direct management entry is `http://127.0.0.1:8765/login.html?role=admin`. In development, the page can load the Management demo account from the local server. Production never exposes demo credentials. After signing in, use **Website content** for approved homepage fields, **Enquiry inbox** for family follow-up and **Merchandise** for the launch catalogue.

Pool water temperature is not inferred from outdoor weather. It remains a daily staff-verified reading unless the venue supplies a compatible sensor feed.

## Data and reset

Local preview data is stored in `data/hv_swim.db`. The database is intentionally excluded from the delivery ZIP so every fresh copy starts with clean seeded demonstration data. Production should use managed PostgreSQL, encrypted backups and environment-specific secrets.

## Original generated website asset

The hero photograph and HV Swim merchandise campaign visual were created with the built-in OpenAI image generation tool for this project. The merchandise visual uses the supplied HV Swim Bendigo logo as its brand reference and is presented as a concept until final products and manufacturer specifications are approved.
