#!/bin/zsh
cd "$(dirname "$0")" || exit 1
hv_preview_port=8765
if [[ ! -x ".venv/bin/python" ]]; then
  echo "Preparing the private HV Swim server environment…"
  python3 -m venv .venv || exit 1
fi
if [[ ! -f ".venv/.hv-ready" || "requirements.txt" -nt ".venv/.hv-ready" ]]; then
  echo "Installing the pinned HV Swim server components…"
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt || exit 1
  touch .venv/.hv-ready
fi
echo "Starting HV Swim Bendigo at http://localhost:$hv_preview_port"
.venv/bin/python -m uvicorn backend.server:app --host 127.0.0.1 --port "$hv_preview_port" &
hv_server_pid=$!
trap 'kill "$hv_server_pid" 2>/dev/null' EXIT INT TERM
for hv_attempt in {1..50}; do
  if curl -fsS "http://localhost:$hv_preview_port/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
open "http://localhost:$hv_preview_port/START_HERE.html"
wait "$hv_server_pid"
