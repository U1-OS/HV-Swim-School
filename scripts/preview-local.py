"""Start a loopback-only demonstration with no inherited integration credentials."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def preview_environment(source):
    # Allow only ordinary OS/runtime configuration; never copy application credentials.
    env = {key: source[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT") if key in source}
    env.update({
        "HV_LOAD_DOTENV": "false",
        "HV_APP_ENV": "development",
        "HV_PUBLIC_URL": "http://127.0.0.1:8772",
        "HV_DATA_DIR": str(ROOT / "data" / "local-preview"),
        "XERO_SYNC_ENABLED": "false",
    })
    return env


if __name__ == "__main__":
    print("HV Swim local preview: http://127.0.0.1:8772", flush=True)
    print("Synthetic records only. Integration credentials and .env are excluded.", flush=True)
    try:
        result = subprocess.run([sys.executable, "-m", "uvicorn", "backend.server:app", "--host", "127.0.0.1", "--port", "8772"], cwd=ROOT, env=preview_environment(os.environ))
        raise SystemExit(result.returncode)
    except KeyboardInterrupt:
        pass
