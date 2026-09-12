#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv312/bin/python ]]; then
  echo 'Prepare the Python 3.12 environment described in README.md first.'
  exit 1
fi
exec .venv312/bin/python scripts/preview-local.py
