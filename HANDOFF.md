# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-30 by Codex — V5.8.0 family safety profiles, private staff merchandise and premium shop complete

## Current state

V5.8.0 is the verified production foundation for the public website, family/staff/
management workspaces, installable PWA, Capacitor mobile shell, premium merchandise
studio and FastAPI service. This release preserves the working V5.7.0 term, absence,
lesson-register and payment-routing workflows.

The public shop is now a family-only premium collection. Staff uniforms are removed from
the public page and public product API, and are available only through authenticated Staff
and Management workspaces. Family accounts now include editable child safety profiles for
emergency contact, allergies, lesson-relevant medication, medical/safety information and
communication, sensory or learning support.

Payment ownership remains explicit. Lesson/term invoices and approved absence-credit
adjustments belong to the Xero invoicing workflow. Approved merchandise belongs to
Shopify Checkout. The platform displays connection/readiness state and never invents a
payment, invoice, credit note, stock record or order when credentials and launch gates are
incomplete.

## Delivered in V5.8.0

- Rebuilt the public shop presentation around premium family swimwear, embroidered towels,
  hooded towel ponchos, goggles/equipment, named drinkware and POD family wear.
- Added a premium shop hero, collection navigation, embroidered-towel feature, family/POD
  collection, supplier-routing explanation, enhanced cards, saved collection and mobile
  refinements without removing the existing static/local-storage preview behaviour.
- Expanded the catalogue from 21 to 24 planned products with a mini hooded towel plus
  premium family tee and crew concepts. All remain sample- and supplier-gated.
- Public `/api/products` excludes every `audience=staff` record in planned, fallback and
  approved Shopify modes. Supplier costs and private provider mappings remain excluded.
- Added role-protected `/api/staff/merchandise` for staff and management only. The Staff
  workspace now has a Staff merch destination showing the eight staff uniform products;
  family products are not mixed into that view.
- Added swimmer allergy, medication and support fields with startup migrations and updated
  development seed data.
- Family → Child details provides editable emergency contact, allergy, medication,
  medical/safety and communication/sensory/learning-support fields for each owned swimmer.
  Photo clearance remains read-only in this quick profile so formal consent is not changed
  accidentally.
- Family safety updates require a customer session, CSRF and swimmer ownership. The audit
  record stores field names only and deliberately excludes the health/allergy text.
- Staff lesson registers display allergy alerts and other relevant safety/support details
  for swimmers in the instructor's assigned classes.
- Management swimmer provisioning supports the same safety fields.
- Privacy, terms, README, merchandise production plan, start page and deployment handoff now
  describe the health-data handling and family/staff merchandise visibility boundary.
- V5.8.0 asset URLs and `v580` service-worker caches force installed PWAs to receive the
  new catalogue and role views.

## Preserved production safeguards

- PBKDF2 passwords, HttpOnly sessions, CSRF, role permissions, sign-in rate limits,
  mandatory first-password change, account suspension/session revocation and audit logs.
- School-term operations, two absence credits per swimmer/term, no automatic make-ups or
  refunds, parent-on-site enforcement and photo-clearance snapshots.
- Staff-verified pool readings with 24-hour freshness, opening checklists, public closure
  alerts and separate Bendigo outdoor weather. Weather never substitutes for pool water.
- Enrolment/capacity/waitlist management, rosters, reviewed timesheets without clock-ins,
  achievements/certificates, support tickets, enquiries, location manager and website editor.
- Protected AUSTSWIM/SWIM/Autism Swim association evidence register with issued-PNG,
  renewal, usage-right and public fail-closed gates. Generic third-party logos remain absent.
- PWA offline/public-data boundaries, native Capacitor shell, local fonts/assets, refined
  logo/imagery, responsive public pages, keyboard/focus/reduced-motion support and SEO/local
  business structure.

## Verification — 30 August 2026

- Python API/security suite: **95 passed, 1 intentionally skipped**.
- Running-server read-only smoke suite: **47 checks passed**.
- Static site checker: **19 pages, 14 precached files and 8 scripts passed**.
- JavaScript syntax and whitespace/error checks passed.
- In-app browser walkthrough covered the public Shop plus signed-in Family Child details and
  Staff merchandise. Desktop and 390×844 mobile views reported zero horizontal overflow,
  the public surface contained no staff product names, the staff view contained exactly
  eight staff-only products, and the browser console reported no warnings or errors.

## External work before production

Follow `PRODUCTION_HANDOFF.md`. Main dependencies remain managed PostgreSQL/Australian
hosting, approved real data, backup/restore and monitoring, legal/WCAG/security review,
MFA/recovery/session controls and an independent penetration test.

HV Swim must provide/configure:

- Existing Xero organisation OAuth and account/tax/contact mappings; implement and test
  idempotent lesson invoices, reconciliation and credit notes. Payroll transmission remains
  locked until real pay periods and duplicate-export protection exist.
- Shopify credentials, approved physical samples, separate customer/staff collection rules,
  product/variant mappings, stock, GST, shipping/returns and an end-to-end test order.
- Approved Printify/VistaPrint/specialist supplier accounts, artwork rights, decoration
  specifications and samples. These are fulfilment routes, not alternative checkout owners.
- A reviewed policy and retention schedule for child health/safety data, least-privilege
  staff access and a real-data migration process.
- Email/SMS and Web Push/APNs/FCM providers, consent/token lifecycle and delivery receipts.
- Current issued association artwork/evidence, external directory corrections, manual vector
  logo/colour files and physical print/embroidery approvals.
- Production HTTPS domain, native Apple/Google accounts, commercial weather arrangement if
  required and a pool sensor only if a reliable venue feed is available.

Do not commit `.env`, databases, generated `www/`, native `ios/`/`android/` folders or delivery ZIPs.
