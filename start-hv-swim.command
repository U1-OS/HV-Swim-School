#!/bin/zsh
cd "$(dirname "$0")" || exit 1
hv_preview_port=8765
hv_venv=.venv312

if [[ ! -x "$hv_venv/bin/python" ]]; then
  hv_python=""
  for hv_candidate in python3.14 python3.13 python3.12 python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if command -v "$hv_candidate" >/dev/null 2>&1 && "$hv_candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
      hv_python="$hv_candidate"
      break
    fi
  done
  if [[ -z "$hv_python" ]]; then
    echo "HV Swim needs Python 3.12 or newer. Install it from python.org, then run this launcher again."
    exit 1
  fi
  echo "Preparing the private HV Swim server environment…"
  "$hv_python" -m venv "$hv_venv" || { echo "Could not create the Python environment."; exit 1; }
fi

if [[ ! -f "$hv_venv/.hv-ready" || "requirements.txt" -nt "$hv_venv/.hv-ready" ]]; then
  echo "Installing the HV Swim server components…"
  if ! "$hv_venv/bin/python" -m pip install --disable-pip-version-check -r requirements.txt; then
    echo
    echo "The install did not finish. The usual causes:"
    echo "  • no internet connection"
    echo "  • a version in requirements.txt that does not exist on PyPI"
    echo
    echo "The message above names the package that failed. Nothing is broken — fix that line"
    echo "and run this file again."
    exit 1
  fi
  touch "$hv_venv/.hv-ready"
fi

# Confirm the server can actually be imported before promising anything.
if ! "$hv_venv/bin/python" -c "import uvicorn, backend.server" >/dev/null 2>&1; then
  echo
  echo "The components installed, but the server could not be loaded. Details:"
  "$hv_venv/bin/python" -c "import uvicorn, backend.server" 2>&1 | tail -5
  exit 1
fi

echo "Starting HV Swim Bendigo at http://localhost:$hv_preview_port"
"$hv_venv/bin/python" -m uvicorn backend.server:app --host 127.0.0.1 --port "$hv_preview_port" &
hv_server_pid=$!
trap 'kill "$hv_server_pid" 2>/dev/null' EXIT INT TERM

hv_started=0
for hv_attempt in {1..80}; do
  if curl -fsS "http://localhost:$hv_preview_port/api/health" >/dev/null 2>&1; then
    hv_started=1
    break
  fi
  kill -0 "$hv_server_pid" 2>/dev/null || break
  sleep 0.1
done

# Opening the browser at a server that never came up just shows a blank page and tells
# nobody anything, so only open it once the health check has actually answered.
if [[ "$hv_started" -eq 1 ]]; then
  open "http://localhost:$hv_preview_port/START_HERE.html"
  echo "Ready. Keep this window open while you are using the site; close it to stop the server."
else
  echo
  echo "The server did not answer on port $hv_preview_port."
  echo "If something else is already using that port, close it and run this file again."
  echo "Any error from the server is printed above."
fi

wait "$hv_server_pid"
