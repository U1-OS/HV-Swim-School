#!/bin/zsh
set -e

PROJECT_DIR=${0:A:h}
cd "$PROJECT_DIR"

echo ""
echo "HV Swim Bendigo · iOS and Android preparation"
echo "------------------------------------------------"

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 22 or newer is required. Opening the official download page."
  open "https://nodejs.org/en/download"
  echo "Install Node.js, then run this file again."
  read -k 1 "?Press any key to close…"
  exit 1
fi

echo "Current bundle ID: au.com.hvswimbendigo.mobile"
echo "Confirm this identifier before the first TestFlight or Play Console upload; store bundle IDs are difficult or impossible to change later."
echo ""
read "MOBILE_URL?Enter the HTTPS production app address (example: https://app.hvswim.com.au): "
if [[ ! "$MOBILE_URL" =~ ^https:// ]]; then
  echo "A real HTTPS address is required for phone builds."
  read -k 1 "?Press any key to close…"
  exit 1
fi

export HV_MOBILE_APP_URL=${MOBILE_URL%/}

echo "Installing the locked mobile build dependencies…"
npx --yes pnpm@11.19.0 install --frozen-lockfile
echo "Building the secure mobile launch shell…"
npx --yes pnpm@11.19.0 run mobile:web

if [[ ! -d ios ]]; then
  echo "Creating the iOS Xcode project…"
  ./node_modules/.bin/cap add ios
fi
if [[ ! -d android ]]; then
  echo "Creating the Android Studio project…"
  ./node_modules/.bin/cap add android
fi

./node_modules/.bin/cap sync

echo ""
echo "Mobile projects are ready."
echo "• Run ./open-ios.command for Xcode"
echo "• Run ./open-android.command for Android Studio"
echo "• Read MOBILE_APP_README.md before signing or store submission"
echo ""
read -k 1 "?Press any key to close…"
