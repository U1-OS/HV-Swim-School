# Security policy and dependency review

Report a suspected vulnerability privately to the repository owner. Do not include real
customer, swimmer, health, payroll or credential data in a public issue.

## Supported deployment

- Python 3.12 or newer on a maintained POSIX/Linux host behind HTTPS.
- A strong deployment-only `HV_SESSION_SECRET` and production host allowlist.
- Managed production persistence, encrypted backups and error monitoring before real data.
- No direct exposure of the source checkout: the server publishes only explicit root files
  and the fixed `assets/` directory.

## 2026 Starlette advisory review

FastAPI 0.128.8 currently constrains Starlette to `<1.0`; the compatible current release
is pinned at 0.52.1. `pip-audit` also reports five advisories whose patched Starlette
versions are 1.x and therefore outside FastAPI's supported range. They are ignored by CI
only after the following application-level review and controls:

- `PYSEC-2026-161` and `PYSEC-2026-248`: requests with a non-rooted path, path separators
  in the Host header or backslashes are rejected before routing. Production also uses an
  exact trusted-host allowlist. Authentication and authorisation never depend on a
  reconstructed request URL.
- `PYSEC-2026-249`: this API has no form-parsing routes. URL-encoded and multipart API
  bodies are rejected before endpoint handling; JSON size limits should also be enforced
  at the production reverse proxy.
- `PYSEC-2026-2280`: this application does not use Starlette `HTTPEndpoint`; every route
  has an explicit HTTP method allowlist.
- `PYSEC-2026-2281`: the supported production target is POSIX/Linux, not Windows. Public
  file serving is fixed-root/allowlisted and request targets containing backslashes are
  rejected.

These are compatibility exceptions, not permanent dismissals. Remove each ignore and
upgrade Starlette as soon as FastAPI officially supports a patched 1.x release. Keep the
GitHub quality workflow and full security/API suite green for every dependency change.
