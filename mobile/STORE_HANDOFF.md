# iOS and Android store handoff

## Release identity

- Proposed app name: **HV Swim Bendigo**
- Proposed bundle/application ID: `au.com.hvswimbendigo.mobile`
- Release line: `5.6.2`
- Category: Education / Sports
- Primary audience: HV Swim families, staff and management

The Account Holder must approve the final app name and bundle ID before the first upload. Apple explains that the bundle ID uniquely identifies the app and cannot be changed after the first App Store Connect upload: https://developer.apple.com/documentation/Xcode/preparing-your-app-for-distribution

## Apple gates

- Install and build with Xcode 26.
- Select the HV Swim Apple Developer team and confirm automatic signing.
- Verify the iOS 26 SDK or later is used for submission.
- Add the 1024×1024 icon, launch treatment, iPhone/iPad screenshots and support/privacy URLs.
- Complete App Privacy and age-rating answers, including data used by third-party services.
- Configure APNs only after alert categories, consent, token retention and opt-out behaviour are approved.
- Upload to TestFlight, test with internal users, then submit through App Store Connect.

Current Apple submission requirements: https://developer.apple.com/app-store/submitting/

## Google Play gates

- Install Android Studio and Android 16 / API level 36.
- Confirm `targetSdkVersion` is API 36 or higher before submission.
- Create an organisation-owned signing key and protect its backup.
- Produce a signed Android App Bundle (`.aab`), not just a debug APK.
- Complete Data safety, content rating, target audience, privacy policy and account-deletion declarations.
- Configure FCM only after alert categories, consent, token retention and opt-out behaviour are approved.
- Test through an internal or closed track before production rollout.

From 31 August 2026, new Google Play apps and updates must target Android 16 / API level 36 or higher: https://developer.android.com/google/play/requirements/target-sdk

## Assets included

- `assets/app-icon-v3-1024.png` — store/master icon source
- `assets/app-icon-v3-512.png` — Android/PWA icon
- `assets/app-icon-v3-192.png` — PWA/home-screen icon
- `assets/app-icon-v3-180.png` — Apple touch icon
- `assets/app-icon-v3-maskable-192.png` and `assets/app-icon-v3-maskable-512.png` — Android mask-safe icons
- `assets/hv-swim-logo-v3.png` — full horizontal brand source
- `assets/hv-swim-mark-v3.png` — simplified app/navigation mark

Run `npx capacitor-assets generate` after the native projects are created to populate required platform icon and splash variants, then inspect every generated asset in Xcode and Android Studio.

## Review boundaries

The current package is code-complete as a native project foundation but is not a signed store binary. Family messaging, staff tickets, achievements and active-page public alerts are present in the connected web experience; true background APNs/FCM delivery is a production integration, not a simulated feature. Store signing, developer verification, production hosting, privacy disclosures, screenshots, beta testing and final review require HV Swim-owned accounts and decisions.
