# Local security review — 13 September 2026

Scope: source review and controlled negative tests against disposable synthetic databases
and the loopback preview. No public host, third-party account or real customer record was
penetration-tested. This is not independent certification, full ASVS verification or a
claim of invulnerability. Root edited; three additional agents independently reviewed
code and reproduced selected findings without editing.

## Findings addressed in this checkpoint

- Account takeover risk: a new provider identity can no longer claim an existing family
  record on matching email alone. Stable provider subject remains the login identity;
  existing profiles require explicit linking. The provider-only linking workflow is next.
- Login abuse: independent account and IP budgets, serialized committed debits, fresh
  credentials/MFA checked under the session transaction, dummy verification for unknown
  accounts, and ASCII-only authenticator codes.
- MFA setup race: fresh account/session checks, locked writes, ten-minute pending setup
  bound to its initiating session, and rejection of already-enabled authenticators.
- Concurrent administrator suspension: serialized final-admin check with revalidation
  that the acting manager is still active.
- Commerce approval bypass: server-side product/sample/supplier/audience/variant checks,
  current variant availability and a separate default-off HV_COMMERCE_LIVE_APPROVED gate.
  Staff uniform checkout is management-only under the newly requested staff boundary.
- Production mistakes: recognized environment names, staging uses production controls,
  published encryption-key placeholder rejected, strict HTTPS origin validation, mandatory
  remote verified-TLS PostgreSQL, and rejection of existing preview data before migrations.
- Error payloads exclude submitted values and validation context. Spreadsheet exports
  neutralize whitespace-prefixed formulas. Secret/key/dump ignore patterns expanded.
- Official CI actions pinned to immutable revisions; weekly dependency checks and
  Dependabot configuration added. These do not activate hosting or transactions.

## Evidence

Initial live loopback HTTP baseline: 20/20 passed. Python dependency audit reports no known
vulnerabilities at this review time, without advisory exclusions. Eleven added focused
security tests pass. Full Python suite: 192 passed, 2 skipped. Mandatory site check passes.
GitHub secret scanning, push protection and dependency security updates are now enabled
and verified through the repository API. CI checkpoint is recorded in HANDOFF.
The prior worker tests protect encoded API routes and prevent private/offline API caching.

## Remaining work and launch boundaries

- In progress by owner request: provider-only sign-in with explicit profile linking,
  restricted staff workspace, management roster editing, owned hours/leave/certificates,
  refreshed planned shop, flags and Acknowledgement of Country.
- Session proof state and inactivity limits, full PostgreSQL recovery rehearsal, retention
  holds/process, deployed TLS/proxy/IP trust/rate limiting, monitoring and incident response
  need verification before accepting real records. Runtime credentials are not source code.
- Domain, hosting, Google/Apple applications and provider callback/sandbox testing need
  owner-controlled accounts. No public deployment, live mail or live finance is approved.
- Commission an independent assessment against the final staging infrastructure, with
  authenticated role coverage and retesting. No test suite can establish zero vulnerabilities.

Review references: [OWASP ASVS/cheat-sheet index](https://cheatsheetseries.owasp.org/IndexASVS.html),
[Google verified identity guidance](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).
