# Handoff — current state

Andrew swaps between Claude and Codex. Read this first and rewrite it last.

**Wheel:** Unassigned
**Last updated:** 2026-08-30 by Codex — V5.9.0 Google/Apple family account access complete

## Current state

V5.9.0 is the verified production foundation for the public website, secure family/staff/
management platform, installable PWA, Capacitor mobile shell, premium merchandise studio
and FastAPI service. It preserves the V5.8 family safety profiles, private staff merchandise,
term/absence/register workflows and the explicit Xero-versus-Shopify payment boundary.

The shared sign-in page now offers Google (including Gmail) and Apple (including iCloud)
sign-up/sign-in for family accounts. The buttons are real integration entry points, but they
stay disabled and visibly say `Setup required` until HV Swim supplies the matching production
credentials. Social sign-up can create or link only customer/family accounts. Staff and
management remain invitation-controlled and cannot self-link through a provider email.

## Delivered in V5.9.0

- Added a premium, accessible Google and Apple family-account section to `login.html`, with
  provider status, terms/privacy links, safe error messages and clear team-account guidance.
- Added Google OpenID Connect authorisation-code flow with PKCE, state and nonce, plus Apple
  authorisation-code flow with the required narrow `form_post` callback.
- Added server-side RS256 signature verification using provider JWKS, including algorithm,
  key ID, issuer, audience/authorised-party, expiry/not-before/issued-at, nonce, subject and
  verified-email checks. Rotated provider keys refresh once when a new key ID appears.
- Added ten-minute OAuth attempt records with SHA-256 state digests, one-time consumption,
  expiry cleanup and a 30-start-per-IP limit. Raw state and provider tokens are not stored.
- Added provider identity records with unique provider/subject and provider/user boundaries.
  New social-only family accounts receive an unknown random password hash, and returning
  verified customer emails can link to the existing family account.
- Provider access, refresh and ID tokens are never persisted or returned to browser code.
  Audit events record only provider and new-account status.
- Apple runtime configuration accepts a generated, time-limited client secret; the Apple
  `.p8` key remains outside this project. Google and Apple credentials stay server-side.
- Added startup migrations for existing V5.8 preview databases and new indexes for transient
  attempt expiry/IP lookup and provider identity lookup.
- Updated `.env.example`, README, privacy, terms, security policy and production handoff with
  the exact external activation and data-handling boundaries.
- Updated the full site and PWA cache line to V5.9.0 / `v590`.

## Verification — 30 August 2026

- Python API/security/crypto suite: **106 passed, 1 intentionally skipped**.
- Running-server read-only smoke suite: **48 checks passed**.
- Static site checker: **19 pages, 14 precached files and 8 scripts passed**.
- Dependency audit: **no unhandled known vulnerabilities**; seven documented Starlette
  compatibility advisories remain application-controlled and ignored as recorded in
  `SECURITY.md` until FastAPI supports the patched Starlette 1.x line.
- JavaScript and Python syntax plus whitespace/error checks passed.
- In-app browser walkthrough covered generic family sign-in, staff invitation-only sign-in,
  safe provider-error display and 390×844 mobile layout. Google/Apple setup states were
  accessible, horizontal overflow was zero and browser console warnings/errors were zero.
- Existing V5.8 database migration was exercised against the local preview database and the
  running V5.9 smoke suite passed afterward.

## Preserved production safeguards

- PBKDF2 passwords, HttpOnly sessions, CSRF, role permissions, password-login rate limits,
  mandatory first-password change, account suspension/session revocation and audit logs.
- School-term operations, two absence credits per swimmer/term, no automatic make-ups or
  refunds, parent-on-site enforcement and photo-clearance snapshots.
- Staff-verified pool readings with freshness rules, separate outdoor weather, pool alerts,
  enrolment/waitlist management, reviewed timesheets without clock-ins and support tickets.
- Family child allergy/medication/safety/support profiles and staff lesson-register alerts.
- Family-only public merchandise, role-protected staff uniforms and fail-closed Shopify,
  Printify and supplier launch gates.
- Protected AUSTSWIM/SWIM/Autism Swim evidence and issued-artwork gates; no generic or
  scraped third-party qualification logos are included.

## External work before production

Follow `PRODUCTION_HANDOFF.md`. Google and Apple cannot be made live from source code alone.
HV Swim must provide/configure:

- Google Cloud OAuth web client, approved consent screen/domain and the exact production
  HTTPS callback; set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI`.
- Apple Developer Services ID, verified domain/return URL and a generated time-limited
  client secret; set `APPLE_CLIENT_ID`, `APPLE_CLIENT_SECRET` and `APPLE_REDIRECT_URI`, then
  schedule secret rotation. Keep the Apple `.p8` signing key outside this repository.
- End-to-end provider testing for new/returning families, Apple private relay emails,
  cancellation, revoked provider consent, account deletion and support recovery.
- Managed PostgreSQL/Australian hosting, backups, monitoring, MFA for management, verified
  recovery/deletion/session controls, legal/WCAG/security review and penetration testing.
- Existing Xero OAuth and mappings; approved Shopify/Printify/specialist suppliers and
  physical samples; email/SMS/Web Push/APNs/FCM delivery; current association evidence;
  commercial weather and a pool sensor only if a reliable venue feed exists.

Do not commit `.env`, databases, generated `www/`, native `ios/`/`android/` folders or delivery ZIPs.
