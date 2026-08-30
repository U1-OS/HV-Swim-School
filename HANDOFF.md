# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-30 by Codex — V5.6 production upgrade complete

## Current state

V5.6 is the verified production foundation for the public website, family/staff/
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

## Delivered in V5.6

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
- Public homepage, cards, motion, spacing, mobile layouts and support launcher received a
  child-friendly premium polish while retaining restrained animation and reduced-motion
  support. Duplicate homepage content was removed and calls to action were simplified.
- Pool conditions never fabricate a temperature: only a staff/sensor-verified reading
  newer than 24 hours is presented as current. Weather remains separate from water data.
- Public prototype/association/merch blocks fail closed behind explicit server flags.
  Management → Staff compliance now records the AUSTSWIM, SWIM Schools Australia and
  Autism Swim publication rules and official links. No third-party mark is shown without
  current issued artwork and usage evidence.
- The 21-product premium catalogue now has enforceable launch blockers for a physical
  sample, costs, variants, supplier route/reference and Shopify/Printify mapping. Supplier
  costs and private mapping IDs no longer leak through public product responses.
- Shopify-connected public products must also pass the local approval gates. Concept
  images and non-live saved lists are labelled honestly; provider implementation details
  stay preview-only.
- Service-worker installation is smaller and safer: 14 core assets instead of the former
  full-site precache, runtime caching for pages/assets, network-only authenticated APIs,
  fresh/no-store public alerts and cached public-data fallbacks.
- V5.6 metadata, mobile/store guides, brand/merch plans, production handoff and automated
  regression checks are aligned.

## Verification — 30 August 2026

- Python API/security suite: **88 passed, 1 intentionally skipped**.
- Running-server smoke suite: **37 checks passed**.
- Static site checker: **19 pages, 14 precached files and 8 scripts passed**.
- JavaScript syntax, whitespace/error checks and Capacitor mobile web-shell build passed.
- Real-browser desktop and 390×844 mobile walkthrough covered all public pages, shop,
  sign-in, management command centre and staff-compliance/badge gates. No horizontal
  overflow, broken visible images or browser console warnings/errors were found.

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
