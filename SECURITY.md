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
- `PYSEC-2026-249`: URL-encoded and multipart API bodies are rejected before endpoint
  handling except the exact Apple OpenID callback required by Apple's `form_post` protocol.
  That endpoint manually decodes a maximum 32 KiB body and does not invoke Starlette's form
  parser. JSON size limits should also be enforced at the production reverse proxy.
- `PYSEC-2026-2280`: this application does not use Starlette `HTTPEndpoint`; every route
  has an explicit HTTP method allowlist.
- `PYSEC-2026-2281`: the supported production target is POSIX/Linux, not Windows. Public
  file serving is fixed-root/allowlisted and request targets containing backslashes are
  rejected.

These are compatibility exceptions, not permanent dismissals. Remove each ignore and
upgrade Starlette as soon as FastAPI officially supports a patched 1.x release. Keep the
GitHub quality workflow and full security/API suite green for every dependency change.

## Family social sign-in

- Google uses an authorisation code with PKCE, state and nonce. Apple uses authorisation
  code, state and nonce with the required form-post callback.
- Provider ID tokens are checked against the provider JWKS, issuer, audience, nonce and
  verified-email claim. Provider access, refresh and ID tokens are never persisted.
- Transient authorisation state is stored only as a SHA-256 digest and expires after ten
  minutes. It is consumed before the code is exchanged so it cannot be replayed. Starts
  are limited per IP address to prevent a client from filling the transient-attempt table.
- A new provider identity can create only a customer/family account. An email matching a
  staff or management account fails closed and requires management approval.
- Keep all client secrets in the deployment secret store. Keep the Apple `.p8` signing key
  outside this project and use it only to generate the rotated Apple client secret. Never
  put either value in browser JavaScript, Git, logs or a support ticket.
