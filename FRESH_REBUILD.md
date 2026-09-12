# Fresh rebuild — 13 September 2026

Andrew explicitly requested a new rebuild based on today’s direction, removing unwanted
old items. Work stays in the sole Developer repository. Branch: `codex/fresh-brand-rebuild`.
The previous verified work is preserved on GitHub as `1f714c2` on `codex/sunlit-rebuild`.

## Design and product decisions

- The existing HV Swim Bendigo logo defines the brand: navy #061A3B, blue #008CCB,
  cyan #19C8F4, gold #FFC928, white. No green/teal interface theme.
- Boutique, welcoming and professional; clear typography and restrained depth. Static,
  fully opaque text. Moving local vector water and subtle brand motion respect pause,
  reduced motion and hidden-tab states. No coarse WebGL backgrounds or card tilting.
- Clear hierarchy: Home → Programs → Locations → Our story → Enquire. Collection is
  secondary and transparently unavailable for ordering until its approvals are complete.
- Remove the floating public message launcher, duplicate mobile booking bars, game/3D
  demos, supplier planning jargon and obsolete theme layers from the new public experience.
  Contact remains accessible through the header, enquiry page and working phone link.
- Honest information: no invented staff, reviews, affiliations, availability, legal
  certification, live delivery or production status. Use the supplied business registration
  facts; Bendigo, Victoria was explicitly reconfirmed. Email/domain remain unverified.
- Existing campaign imagery stays labelled illustrative pending approved real photography.
  Existing source images are used within a sensible pixel budget, never artificially upscaled.

## Architecture and preservation

Public pages will load a single fresh `assets/site.css` design system and `assets/site.js`
controller. Preserve tested lesson-pathway and enquiry behaviour, adapting DOM hooks
explicitly. Backend, encrypted records, role permissions, calendar, held mail, finance
boundaries, account security and source-controlled tests remain intact.

The protected workspaces remain available throughout migration and receive a deliberate
clean visual migration after the public journey. Do not hide missing features behind
placeholder buttons or overwrite local runtime data. The native mobile app remains paused.
Obsolete source/assets can be removed once all entry-point, JS, CSS, service-worker and
backend references have been checked. Git history is the archive; no duplicate served build.

## Delivery sequence

1. Clean shared foundation and homepage, then programs, venues and About.
2. Preserve and restyle the four-step enquiry, general contact and success/error states.
3. Simplify prelaunch collection and rebuild legal/help pages around accurate current facts.
4. Clean up protected-workspace presentation; remove superseded files only after references
   and role workflows pass. Update service-worker caches and static checks.
5. Browser review at desktop/tablet/phone, keyboard/motion/error/offline checks, regression
   suites and controlled local security checks; update handoff, commit and push each checkpoint.

## Remaining business inputs / approval gates

No domain or hosting account exists yet. Verify the business mailbox before publishing a
working email link. Confirm private pricing, current term dates, arrival/access details,
approved real photos and named safeguarding contacts. Obtain legal/privacy review and any
third-party artwork rights. Configure providers privately and test in approved sandboxes.
Public deployment, outbound messages and live financial transactions need explicit approval.

The broader registration-resource workflow, scheduled notices/CMS, safeguarding policies,
PostgreSQL recovery and final handover remain in scope; this is not a completed launch.

## Fresh 1 implementation — 13 September 2026

Completed the six primary public pages, seven information/policy pages, branded 404 and
offline guidance, plus sign-in: 16 fresh pages. `site.css`/`site.js` are the new shared
foundation; `collection.css` and `auth.css` style their focused surfaces. Original logo
and existing campaign assets are retained. Product and campaign imagery is illustrative.

Removed active public legacy style/experience/support loads, public-api.js, WebGL
`aquatic-scene.js` and its retired test, layered shop-v55.css, the 3D pool/bottle demos,
kit planning controls, public supplier-routing exposition, duplicated mobile commerce bar,
and optional embedded Facebook feed. Phone and enquiry routes replace unverified mailbox
links. Kept catalog search/filter/pagination/details and approved-provider basket boundaries.
Unapproved products have no published prices, active purchase controls or claimed stock.

The program matcher, private-price boundary, readiness rules, four-step enquiry,
non-lesson contact path, protected account services and permission checks remain connected.
Enquiry, recovery and password-link forms have explicit POST fallbacks; personal values
must not enter GET URLs if a controller fails. Unconfigured social sign-in options remain
hidden; existing email/password sign-in is available immediately.

Public conditions reject old/future readings and refresh while visible. Alerts retain
venue and time. Preview disclosure is immediate on loopback. Motion honors OS preference,
saved pause, blocked storage and hidden tabs; text/cards are never tilted or faded.

### Security correction

A read-only synthetic review reproduced an old worker flaw: encoded API paths could
fall through to generic navigation caching, despite private/no-store. The worker now
decodes classification, caches only explicitly allowed public HTML navigations, honors
private/no-store and never caches API responses. Runtime/core revisions expire earlier
caches, including the old public-data cache. Offline stock, availability and venue status
fail visibly rather than presenting an indefinite cached response as current.

### Verification

- Mandatory static checks: 23 HTML pages, 20 core precache entries, 11 JS controllers.
- Seven Node suites pass: fresh public behavior, service-worker private-data isolation,
  remaining legacy experience, Melbourne/DST dates, login safety, logout recovery and
  lesson-readiness/pathway contracts. New suites run in GitHub CI.
- Backend regression: 181 passed, 2 skipped (86.83 seconds). Existing dependency
  deprecation warnings remain; no failing test. PostgreSQL remains covered by CI.
- Browser: all 15 fresh public pages at 390px with no horizontal overflow, broken loaded
  images or legacy styles. Desktop homepage/sign-in and product dialog visually reviewed.
- Guided enquiry validation and full submission returned synthetic `HV-ENQ-0030`; form
  hidden, success visible. Reserved address qa-fresh-preview@example.com; runtime record
  stays local and ignored. No outbound delivery or payment.
- Program matcher for a cautious 6–8-year-old seeking technique recommends Learn to Swim;
  age/confidence/goal survive the enquiry handoff. General contact mode skips lesson steps
  and requires a message. Motion pause persists and cookie controls clear preferences.
- Collection search returned three towels; product details and disabled ordering checked.
  Family sign-in reached the protected account and role-appropriate workspace.

### Still required

The existing protected operations workspace is preserved, not yet rebuilt in the new
foundation. Its broader visual migration and deep state review remain separate work.
Registration-resource issuing, scheduled CMS/notice archive, approved safeguarding/policy
workflow and PostgreSQL full recovery from the larger master brief remain unfinished.
A production retention/legal-hold process needs owner and professional review; closed
local enquiries currently age out at startup after 183 days without a legal-hold field.

Owner inputs remain: domain/hosting, verified mailbox, current term/arrival details,
private prices/durations, real approved photography, approved policies and safeguarding
contacts, product samples/pricing/rights and private provider configuration. Public launch,
external messages and live financial transactions remain unapproved. This checkpoint is
not sale certification, legal certification, full WCAG conformance or an independent pentest.
