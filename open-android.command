#!/bin/zsh
set -e
PROJECT_DIR=${0:A:h}
cd "$PROJECT_DIR"
if [[ ! -d android ]]; then
  echo "Run prepare-mobile-app.command first."
  read -k 1 "?Press any key to close…"
  exit 1
fi
npx cap open android
