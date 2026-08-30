# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-30 by Codex — V5.7.0 term operations, lesson registers and payment routing complete

## Current state

V5.7.0 is the verified production foundation for the public website, family/staff/
management workspaces, installable PWA, Capacitor mobile shell, premium merchandise
studio and FastAPI service. This release preserves the working V5.6.2 system and converts
four confirmed business rules from copy into audited operations: term dates, two absence
credits per swimmer per term, parent/guardian presence except Stroke Development, and no
photos without recorded clearance.

Payment ownership is now explicit. Lesson/term invoices and approved absence-credit
adjustments belong to the Xero invoicing workflow; merchandise and staff uniforms belong
to Shopify Checkout. The platform displays connection/readiness state and never invents a
payment, invoice, credit note or order when credentials and launch gates are incomplete.

The repository remains deliberately honest about external boundaries. SQLite, bundled
accounts and the dynamic “Preview operating term” are development-only. Production starts
without invented term dates. Xero invoice/credit-note creation and payroll transmission,
Shopify launch, email/SMS/background push, pool sensors, native signing and managed
PostgreSQL still require HV Swim-owned accounts, approved data and deployment work.

## Delivered in V5.7.0

- Added school-term, absence-report and lesson-attendance records with database constraints,
  indexes, role ownership, CSRF protection and audit events.
- Management → Term operations can create draft terms, activate approved terms, close the
  previous active term automatically and review term/credit history. The local preview term
  is visibly labelled and is never seeded in production.
- Public “today” venue lessons and class availability are term-aware. Recurring timetable
  entries no longer present themselves as current when no active/published term covers the
  date. Closed venues also suppress today’s lessons.
- Family → Report an absence shows each swimmer’s two-credit allowance, the next valid date
  for every confirmed recurring lesson and the full credit ledger. First two eligible
  reports are marked credited; later absences remain recorded without an extra credit.
- Absence reporting accepts only owned, confirmed bookings, today/future dates matching the
  class weekday and the active term. Duplicate reports are blocked. Only a general reason
  category is collected; no detailed medical explanation is requested.
- The family workflow states the confirmed $22.50 term fee, no make-up/no mid-term-refund
  policy and the financial boundary: eligibility is recorded but no Xero invoice, refund
  or credit note is changed automatically.
- Staff → Lesson register provides date-based assigned classes, safety/support notes,
  family-reported absence state, attendance, parent-on-site confirmation, photo-clearance
  snapshot and a privacy-limited internal note. Future attendance cannot be pre-recorded.
- Non-Stroke present/late records require parent/guardian confirmation. Stroke Development
  is labelled as the approved exception. Staff can change only their assigned classes;
  management can review all registers.
- The attendance record keeps its term link and an audit-safe snapshot of parent/photo
  safeguards without writing the private note into the audit log.
- Management → Integrations includes a payment-routing matrix: Xero for lesson/term finance
  and absence adjustments, Shopify for merchandise/uniform checkout. Each row declares its
  live-transaction blocker separately from connection status.
- Family class finder and public/legal copy now explain the Xero lesson-invoice route, while
  the merchandise studio remains Shopify-only and sample-gated.
- Added mobile quick access for Family Absences, Staff Lesson Register and Management Term
  operations/registers. New screens use the existing premium role colours, cards, focus
  states and responsive tables.
- Replaced the Locations page’s hard-coded indicative lesson rows with server-connected,
  term-aware venue lessons and improved the small-screen location condition layout.
- V5.7.0 asset URLs and v570 service-worker caches force installed PWAs to receive the
  new management and register code.
- Expanded regression coverage for the two-credit limit, duplicate reports, ownership,
  future-attendance blocking, staff assignment, parent-on-site enforcement, photo snapshots,
  term creation/activation and Xero/Shopify routing.

## Preserved V5.6 production safeguards

- PBKDF2 passwords, HttpOnly sessions, CSRF, role permissions, sign-in rate limits,
  mandatory first-password change, account suspension/session revocation and audit logs.
- Staff-verified pool readings with 24-hour freshness, opening checklists, public closure
  alerts and separate Bendigo outdoor weather. Weather never substitutes for pool water.
- Enrolment/capacity/waitlist management, rosters, reviewed timesheets without clock-ins,
  achievements/certificates, tickets, enquiries, location manager and website editor.
- Protected AUSTSWIM/SWIM/Autism Swim association evidence register with issued-PNG,
  renewal, usage-right and public fail-closed gates. Generic third-party logos remain absent.
- Twenty-one-product premium merchandise production plan with physical-sample, cost,
  supplier, mapping and Shopify publication gates; private costs/mapping IDs stay private.
- PWA offline/public-data boundaries, native Capacitor shell, local fonts/assets, refined
  logo/imagery, responsive public pages, keyboard/focus/reduced-motion support and SEO/local
  business structure.

## Verification — 30 August 2026

- Python API/security suite: **93 passed, 1 intentionally skipped**.
- Running-server read-only smoke suite: **43 checks passed**.
- Static site checker: **19 pages, 14 precached files and 8 scripts passed**.
- JavaScript syntax, Python compilation, whitespace/error checks and the Capacitor mobile
  web-shell build passed.
- Chrome walkthrough covered the public homepage, Locations and Shop plus signed-in Family
  Absences, Staff Lesson Register and Management Term operations. Desktop and 390×844
  mobile role views reported zero horizontal overflow. A populated staff register was also
  checked at desktop size; the location and register alignment issues found during QA were
  corrected.

## External work before production

Follow PRODUCTION_HANDOFF.md. Main dependencies are managed PostgreSQL/Australian hosting,
approved real data, backup/restore and monitoring, legal/WCAG/security review, MFA/recovery/
session controls and an independent penetration test.

HV Swim must provide/configure:

- Approved real term dates plus public holidays, venue closures and one-off exceptions.
- Existing Xero organisation OAuth and account/tax/contact mappings; implement and test
  idempotent lesson invoices, payment-service handling, reconciliation and credit notes.
  Payroll also remains a separate locked readiness workflow until pay periods and duplicate
  export protection are implemented.
- Shopify credentials, approved sampled products, supplier/store mappings, stock, variants,
  GST, shipping/returns and a successful end-to-end test order. Printify/VistaPrint/
  specialist suppliers remain downstream production routes, not alternative checkout owners.
- Email/SMS and Web Push/APNs/FCM providers, consent/token lifecycle and delivery receipts.
- Current issued association artwork/evidence, external directory corrections, manual vector
  logo/colour files and physical print/embroidery approvals.
- Production HTTPS domain, native Apple/Google accounts, commercial weather arrangement if
  required and a pool sensor only if a reliable venue feed is available.

Do not commit `.env`, databases, generated `www/`, native `ios/`/`android/` folders or delivery ZIPs.
