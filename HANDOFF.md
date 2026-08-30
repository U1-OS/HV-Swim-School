# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-30 by Codex — V5.6.2 association evidence workflow complete

## Current state

V5.6.2 is the verified production foundation for the public website, family/staff/
management workspaces, installable PWA, Capacitor mobile shell, merchandise studio and
FastAPI service. It preserves the working V5 architecture while substantially tightening
public truthfulness, responsive polish, operational workflows, legal/business copy,
commerce gates, service-worker performance and production documentation.

The repository remains deliberately honest about external boundaries. The app is a
working PWA and Capacitor-ready foundation, not a signed App Store/Google Play release.
Active pages receive public alerts, but background Web Push/APNs/FCM, email and SMS need
real providers. Pool temperatures are staff-verified until a compatible sensor feed is
selected. Xero OAuth/readiness exists, but payroll transmission remains locked. SQLite
and demo accounts are preview-only and must not hold real customer, child or payroll data.

## Delivered in V5.6.2

- Management → Staff compliance now contains a complete protected register for the
  AUSTSWIM, SWIM Schools Australia and Autism Swim marks. Each record captures its
  membership/certificate reference, valid-until date, internal evidence note, exact PNG,
  explicit usage-right confirmation and management reviewer/time.
- PNG uploads are JSON/base64 rather than multipart, limited to 1 MB and 64–2400 pixels,
  structurally/CRC validated and stored under a content hash. Public and management image
  routes re-check SHA-256 integrity before considering artwork available.
- The public badge endpoint exposes no private evidence fields and returns nothing until
  all three records pass and Management → Website content separately requests release.
  Expiry, withdrawn rights, missing artwork or a changed file automatically hides the
  complete homepage and footer section; text placeholders are no longer shown publicly.
- The evidence manager has polished desktop and single-column mobile cards, file guidance,
  official requirement/directory links, visible blockers and a clear ready state. Staff
  cannot access the management register; every save is audited without logging private
  notes or full references.
- `HV_DATA_DIR` now works as a real environment override so SQLite preview data and private
  runtime badge artwork can sit on an encrypted persistent volume. Production still must
  move customer operations to managed PostgreSQL and persist or replace the artwork store.

- Confirmed HVS BENDIGO PTY LTD identity, ABN, business/postal details and primary email
  are carried through the footer, structured data, privacy, terms and handoff material.
- Confirmed operating rules are consistent across programs, enquiry, FAQ and legal pages:
  $22.50 per lesson billed by term and due on enrolment; two absence credits per term; no
  make-up classes; no mid-term refund subject to ACL; parent onsite except Stroke
  Development; and no photos without class/swimmer clearance.
- Paul and Laura Smith are named as complaint/question contacts. Public enquiries are
  purged after six months. Staff-record retention is documented to the end of the relevant
  financial year, pending final legal/payroll confirmation.
- Clock-in controls and geolocation capture are removed. The legacy clock API returns 410;
  the staff workflow is published roster plus reviewed shift start/finish timesheets.
- Public homepage, cards, motion, spacing, mobile layouts and support launcher retain the
  child-friendly premium polish while retaining restrained animation and reduced-motion
  support. Duplicate homepage content was removed and calls to action were simplified.
- Pool conditions never fabricate a temperature: only a staff/sensor-verified reading
  newer than 24 hours is presented as current. Weather remains separate from water data.
- Public prototype/association/merch blocks fail closed behind explicit server flags.
  No third-party mark is shown without current issued artwork, live renewal evidence,
  verified usage rights, management review and the separate website release switch.
- Management → Website content now shows polished release-gate controls for homepage
  merchandise and qualification/member marks. The server—not only the interface—blocks
  concept products without approved samples/costs/mappings and blocks association marks
  without issued artwork, current evidence and usage rights.
- The Website content workspace also presents the confirmed entity, ABN, primary email,
  complaint contacts, lesson fee and no-clock-tracking rule as locked source-controlled
  business settings, avoiding accidental one-page identity changes.
- The 21-product premium catalogue now has enforceable launch blockers for a physical
  sample, costs, variants, supplier route/reference and Shopify/Printify mapping. Supplier
  costs and private mapping IDs no longer leak through public product responses.
- Shopify-connected public products must also pass the local approval gates. Concept
  images and non-live saved lists are labelled honestly; provider implementation details
  stay preview-only.
- Service-worker installation is smaller and safer: 14 core assets instead of the former
  full-site precache, runtime caching for pages/assets, network-only authenticated APIs,
  fresh/no-store public alerts and cached public-data fallbacks.
- V5.6.2 asset URLs and cache names force existing installed apps to receive the new
  management code instead of retaining a cached V5.6.1 screen.
- V5.6.2 metadata, mobile/store guides, brand/merch plans, production handoff and automated
  regression checks are aligned.

## Verification — 30 August 2026

- Python API/security suite: **90 passed, 1 intentionally skipped**.
- Running-server smoke suite: **39 checks passed**.
- Static site checker: **19 pages, 14 precached files and 8 scripts passed**.
- JavaScript syntax, whitespace/error checks and Capacitor mobile web-shell build passed.
- Real-browser desktop and 390×844 mobile walkthrough covered management sign-in, the
  complete association evidence manager and the public fail-closed state. All three forms
  were accessible, the mobile cards stayed within the viewport, no placeholder mark leaked
  publicly and no browser console warning/error was found.

## External work before production

Follow `PRODUCTION_HANDOFF.md`. Main dependencies are managed PostgreSQL/Australian
hosting, final legal/WCAG/security review, production auth/MFA/recovery, approved real data,
backups/monitoring, term dates and an independent penetration test.

HV Swim must provide/configure:

- Shopify and Printify credentials, supplier mappings, approved physical samples,
  supplier-authorised imagery, variants, pricing, shipping/returns and a full test order.
- Xero organisation OAuth, staff/pay-calendar mappings and approved idempotent payroll
  export rules; the current system never sends payroll.
- Email/SMS and Web Push/APNs/FCM providers, sender verification, consent, token retention,
  delivery/opt-out behaviour and Apple/Google developer/signing accounts.
- A production HTTPS domain, commercial weather arrangement if required and a compatible
  pool sensor only if automatic water temperatures are wanted.
- Current issued AUSTSWIM/SWIM/Autism Swim badge files plus membership/renewal/usage-right
  evidence. Correct external directory details that still disagree with HV Swim's current
  records, including the outdated Autism Swim person listing.
- A manually checked vector logo, CMYK/spot colours, authorised blank-brand suppliers and
  physical print/embroidery samples before bulk merchandise production.

Do not commit `.env`, databases, generated `www/`, native `ios/`/`android/` folders or
delivery ZIPs.
