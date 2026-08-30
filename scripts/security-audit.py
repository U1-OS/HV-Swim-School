#!/usr/bin/env python3
"""Non-destructive HTTP security baseline for a running HV Swim preview."""

from __future__ import annotations

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8768").rstrip("/")
checks: list[tuple[str, bool, str]] = []


def request(path: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None):
    req = Request(BASE + path, method=method, data=data, headers=headers or {})
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def expect(name: str, condition: bool, detail: str) -> None:
    checks.append((name, condition, detail))


status, headers, _ = request("/index.html")
header_names = {name.lower(): value for name, value in headers.items()}
expect("Public website responds", status == 200, f"HTTP {status}")
expect("Content Security Policy", "content-security-policy" in header_names and "object-src 'none'" in header_names.get("content-security-policy", ""), header_names.get("content-security-policy", "missing"))
expect("Clickjacking boundary", "frame-ancestors 'self'" in header_names.get("content-security-policy", "") or "frame-ancestors 'none'" in header_names.get("content-security-policy", ""), header_names.get("content-security-policy", "missing"))
expect("MIME sniffing disabled", header_names.get("x-content-type-options") == "nosniff", header_names.get("x-content-type-options", "missing"))
expect("Referrer policy", header_names.get("referrer-policy") == "strict-origin-when-cross-origin", header_names.get("referrer-policy", "missing"))
expect("Cross-origin opener isolation", header_names.get("cross-origin-opener-policy") == "same-origin", header_names.get("cross-origin-opener-policy", "missing"))

for path in ("/.env", "/data/hv_swim.db", "/backend/server.py", "/.git/config"):
    status, _, _ = request(path)
    expect(f"Sensitive file blocked: {path}", status == 404, f"HTTP {status}")

for path in ("/api/customer/swimmers", "/api/staff/roster", "/api/admin/lesson-charges"):
    status, _, _ = request(path)
    expect(f"Unauthorised API blocked: {path}", status == 401, f"HTTP {status}")

for path in ("/app.html", "/mobile-shell.html"):
    status, _, _ = request(path)
    expect(f"Paused app route blocked: {path}", status == 404, f"HTTP {status}")

status, _, _ = request("/", method="TRACE")
expect("TRACE disabled", status == 405, f"HTTP {status}")

status, _, _ = request(
    "/api/auth/login",
    method="POST",
    data=b"email=test&password=test",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
expect("Unexpected form body rejected", status == 415, f"HTTP {status}")

status, _, _ = request(
    "/api/auth/login",
    method="POST",
    data=b"{}",
    headers={"Content-Type": "application/json", "Content-Length": "2000001"},
)
expect("Oversized API body rejected", status == 413, f"HTTP {status}")

status, _, body = request(
    "/api/auth/login",
    method="POST",
    data=json.dumps({"email": "' OR 1=1 --", "password": "' OR 1=1 --"}).encode(),
    headers={"Content-Type": "application/json"},
)
expect("SQL-injection login rejected", status in {401, 422}, f"HTTP {status}: {body[:100]!r}")

status, headers, _ = request("/api/public/locations", headers={"Origin": "https://attacker.invalid"})
cors = {name.lower(): value for name, value in headers.items()}
expect("Untrusted CORS origin denied", status == 200 and "access-control-allow-origin" not in cors, f"HTTP {status}; ACAO={cors.get('access-control-allow-origin', 'absent')}")

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {name} — {detail}")
print(f"\n{passed}/{len(checks)} security baseline checks passed against {BASE}")
raise SystemExit(0 if passed == len(checks) else 1)
