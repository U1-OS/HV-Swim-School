# Logo-led colour and motion — UI24

Date: 13 September 2026. Owner direction: use the existing logo’s navy, blue, cyan,
gold and white; remove the green/teal interface and add a moving logo/background.
This is a local design checkpoint within the ongoing master rebuild.

## Delivered

- Shared dark brand palette across public pages and protected-page presentation.
- Original logo artwork preserved, with a brief arrival and gentle vertical float.
- Two local CSS water layers using `assets/brand-water-waves.svg`; no external animation
  service, new dependency or background JavaScript timer. Existing optional low-power
  WebGL hero rendering is more visible and still pauses offscreen.
- Persistent pause/resume control; OS reduced motion takes priority. Hidden tabs pause
  pseudo-element animations too. Background layers ignore pointer input and are hidden
  when printing. On phones the 44px control sits above the booking bar.
- Fixed pale-on-white remnants in enquiry/review/success, program comparisons/checklists,
  support dialogs, About panels, venue comparisons and shop controls.
- Program class-selection ticks are hidden until selected, and decorative ticks are
  excluded from accessible radio labels. New management screens have appropriate nav groups.
- Synchronized UI24 asset URLs and service-worker caches; the new water SVG is precached.

## Verification

- Required static site checker: 22 pages, 17 precache entries and 12 JavaScript files.
- Existing JavaScript interaction suites cover scene input, reduced/saved motion,
  unavailable WebGL, date handling, lesson matcher, sign-in and sign-out.
- Browser: homepage at 1440px and 390px; pause stops both logo and background; pause
  survives reload; resume works. The mobile navigation and motion controls remain distinct.
- A synthetic local enquiry traversed all four steps and returned `HV-ENQ-0029`.
  Reserved `.invalid` email was rejected by validation, then `qa-brand-preview@example.com`
  was accepted. No real family data, payment or outgoing delivery was used.
- Support dialog visually reviewed at 390px. Program comparison and checklist computed
  foreground/background colours verified after corrections. Public-page DOM checks
  found no horizontal document overflow in the inspected 390px views.
- Additional solid-background contrast screening identified and corrected inherited
  light-edition surfaces. This screening excludes photographs, gradients and alpha
  compositing, so it is not a claim of complete WCAG conformance.
- Prior UI22 GitHub run `34700306682` passed website, backend/dependency audit and
  PostgreSQL jobs. UI24 changes are presentation/ARIA/cache metadata and handoff updates;
  unchanged backend test results are recorded in `OPERATIONS_SECURITY_UPGRADE.md`.

## Remaining work

The master rebuild is still in progress. Registration resource/version/issue workflows,
scheduled notices/CMS, Victorian child-safety review material, PostgreSQL recovery bundles
and full production handover remain tracked in `HANDOFF.md`. Native Safari/iPhone and
VoiceOver verification, approved real photography and business content are still open.
No public deployment or live transactions are authorised by this checkpoint.

## Downloadable logo files

- `assets/hv-swim-logo-v3-master.png`: high-resolution transparent full-colour master.
- `assets/hv-swim-logo-v3.png`: optimised transparent website version.

These existing images were not regenerated or recoloured. Professional vector artwork
and physical samples remain prerequisites for bulk merchandise production.
