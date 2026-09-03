# Security policy

## Approval demonstrations

`APPROVAL_DEMO` runs the complete product workflow with non-cash demo credits so reviewers can test every feature. It does not authorise real-money collection or payout. The server accepts only `SOCIAL_PREVIEW` and `APPROVAL_DEMO`; any other configured operating mode fails at startup. Approval-demo databases and uploaded evidence must remain isolated from any future licensed production environment.

Do not place credentials, signing keys, payment secrets, stream keys, personal
data, or production database exports in this repository.

## Current security boundaries

- API, upload, and media-control payloads must be treated as untrusted input.
- Authentication and responsible-gambling restrictions must be enforced by the
  backend. Browser storage is not an enforcement boundary.
- Wallet mutations and bet settlement must be atomic, idempotent, authorized,
  auditable, and tested under concurrency.
- Player and staff sessions are opaque, server-side, revocable records. Session
  cookies are HttpOnly and SameSite, and state-changing requests require the
  matching session-bound CSRF token.
- Browser storage must never contain session or refresh bearer tokens, and
  long-lived credentials must not be placed in media or navigation query strings.
- `ROOSTERRUN_OTP_TEST_MODE` is only for isolated automated tests and must never
  be configured on an internet-accessible environment.
- Payment screenshots and payout evidence are stored in private storage and
  served only through ownership- or role-checked API routes, never `/uploads/`.
- `/health/ready/` rejects incomplete production configuration, including a
  non-TLS/non-PostgreSQL database, missing admin or SMS provider, stale secrets,
  unavailable media plane, absent off-host recovery evidence, missing external
  alerts, insecure cookies, unwritable storage, or stopped workers.
- The HTTP runtime caps concurrent requests, times out stalled clients, redacts
  sensitive query parameters from structured logs, exposes private-network
  Prometheus metrics, and handles SIGTERM gracefully.
- Production secrets are loaded from mounted files. Rotate internal secrets at
  least every 90 days; the streaming hook accepts only the current and previous
  generation during a controlled restart.
- Monitoring ingestion is bearer-authenticated and blocked at the public Caddy
  boundary. Alert deliveries use a durable retry outbox and never include
  credentials in payloads or logs.
- Identity documents are stored in the private data tree and are never served
  by `/uploads/`. Only an authenticated administrator with the `compliance`
  permission can retrieve one through the protected document endpoint.
- Do not collect Aadhaar images or Aadhaar numbers. A future Aadhaar option must
  implement UIDAI-approved secure offline verification, consent, minimisation,
  and retention controls.
- `SOCIAL_PREVIEW` is a server-enforced operating mode. Do not add a browser or
  ordinary administrator toggle that enables real-money deposits or bets.
- Recovery archives are stored only in the private data tree and require the
  `operations` permission. They contain credential hashes, financial records,
  payment proofs, and identity files; never copy them into `/uploads/` or source
  control. Verify SHA-256 before any offline restore.
- Reconciliation reports evidence but never repairs wallets automatically.
  Investigate every finding, preserve the audit trail, and use a separately
  reviewed repair procedure when correction is necessary.
- Support references must be resolved against the authenticated player on the
  server. Never trust a player-supplied payment or bet identifier by itself.
- Internal support notes must be filtered by the database query and never sent
  to the player client. A CSS or browser-only visibility rule is not a security
  boundary.
- Financial intelligence signals are evidence for human review, not proof of
  wrongdoing. Detection code must never automatically move funds, settle bets,
  reject payments, or suspend players.
- Intelligence exports are private financial records. Require the dedicated
  permission, use no-cache download headers, and never publish them under the
  public upload path.

## Reporting

Report vulnerabilities privately to the repository owner. Do not include real
user data, usable credentials, or production secrets in an issue or test case.
