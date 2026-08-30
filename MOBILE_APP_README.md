# HV Swim Bendigo mobile app · V5.6.2

This release contains two related mobile products:

1. The working Progressive Web App can be installed from Safari, Chrome or Edge today.
2. The Capacitor 8 foundation creates real Xcode and Android Studio projects for TestFlight, the App Store and Google Play once the production website, developer accounts and signing details are available.

## Prepare the native projects on this Mac

1. Deploy the HV Swim website and API to one approved HTTPS origin.
2. Confirm the final bundle ID in `capacitor.config.json`. The current proposed ID is `au.com.hvswimbendigo.mobile`.
3. Double-click `prepare-mobile-app.command` and enter the production HTTPS address.
4. The launcher installs the Capacitor packages, builds the native launch shell, creates `ios/` and `android/`, and synchronises both projects.
5. Use `open-ios.command` for Xcode or `open-android.command` for Android Studio.

The native shell deliberately does not embed a fake local backend. It checks the approved production service and then opens the connected app. This keeps bookings, staff records and management actions on the protected server rather than storing a second ungoverned database inside each phone.

## Mac requirements

- Node.js 22 or newer
- Xcode 26 and an Apple Developer team for iOS/iPadOS signing and TestFlight
- Android Studio with the Android 16 / API 36 SDK for Google Play submission
- A Google Play Console organisation account
- A production HTTPS origin, final privacy policy and support URL

The launcher detects missing Node.js. Xcode and Android Studio still need to be installed through Apple and Google respectively because they are large, account-bound development tools.

## Mobile features already present

- Role-specific family, staff and management workspaces
- App-style bottom navigation and safe-area layouts
- Bookings, live class capacity and waitlists
- Family messages with staff-visible ticket threads and replies
- Swimmer achievements with family-visible evidence and printable certificates
- Rosters, reviewed timesheets and pool readings without clock-in or continuous location tracking
- Staff ticket triage plus management alerts for closures, changes and reopenings
- Management enrolment desk, approvals, website controls and 21-product merchandise workflow
- Installable icons, standalone display mode and offline app shell
- Live connection checking before opening the native connected experience
- Smart installed/native launch mode that checks the current session and prioritises the correct secure workspace

## Production work before submission

- Replace demo accounts and migrate approved production data.
- Complete privacy, child-safeguarding, retention and account-deletion policies.
- Configure production email/SMS/Web Push/APNs/FCM providers and notification consent. V5.6.2 browser alerts update while the site is open; background native delivery is not claimed yet.
- Test denied geolocation, offline mode, expired sessions and password recovery.
- Add native screenshots, store copy, support contact and privacy disclosures.
- Test iPhone, iPad and Android physical devices before beta distribution.
- Use TestFlight and a closed Google Play testing track before public release.

See `mobile/STORE_HANDOFF.md` for the release gates and current platform requirements.
