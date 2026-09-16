#!/bin/sh
set -eu

cd /app

HOST="${HV_UVICORN_HOST:-127.0.0.1}"
PORT="${HV_UVICORN_PORT:-8000}"

# Keep in sync with HV_TRUSTED_PROXIES (see deploy/LAUNCH_PREPARATION.md).
if [ -n "${HV_FORWARDED_ALLOW_IPS:-}" ]; then
  ALLOW="${HV_FORWARDED_ALLOW_IPS}"
elif [ -n "${HV_TRUSTED_PROXIES:-}" ]; then
  ALLOW="${HV_TRUSTED_PROXIES}"
else
  echo "HV_TRUSTED_PROXIES or HV_FORWARDED_ALLOW_IPS is required for production Uvicorn." >&2
  exit 1
fi

exec python -m uvicorn backend.server:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips="${ALLOW}"
