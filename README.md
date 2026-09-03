# RoosterRun cockfight workspace

This repository now contains one complete cockfight platform: the player PWA,
administrator console, browser broadcast studio, authoritative backend,
persistent database, production container stack, and automated regression
coverage. Legacy multi-game code and duplicate prototypes have been removed.

## Included

- `web/play/` — rebuilt browser/PWA client and reusable interface modules
- `web/admin/` — standalone administration console for operations and branding
- `web/broadcast/` — camera/mobile browser broadcaster
- `server/` — authentication, cockfight, streaming, payments, compliance,
  support, operations, risk, and financial-intelligence engines
- `deploy/production/` — HTTPS application and SRS media-plane stack

Legacy multi-game dashboards, placeholder game cards, and obsolete mobile
multi-game fragments have been removed. The alternate `web/v2/` prototype was
also removed so the project has one canonical player experience.

## Frontend architecture

The production interface is deliberately split into small reusable modules:

- `components.js` — headers, navigation, app shell, dialogs, stream frame,
  outcome cards, result rows, and bet rows
- `ui.js` and `icons.js` — shared formatting, safe rendering, buttons, status
  badges, and inline SVG icons
- `store.js` — predictable application state and rendering notifications
- `api.js` — authenticated API requests, CSRF protection, and error handling
- `streaming.js` — YouTube, HLS/video, and low-latency SRS WHEP playback
- `simulator.js` — local scheduling, odds, playback, result, and settlement lab
- `app.js` — route views, workflows, API normalization, and event handling
- `styles.css` — one responsive design system for public and player pages

The local preview includes clearly marked sample match, result, wallet, and bet
data. Administration is separated from the player application at `/admin/`.

## Unified admin console

The new administration application replaces the legacy embedded admin and
arena-lab screens. It includes overview, users, games/live control, manual
payments, banners, VIP tiers, theme and logo, social links, platform settings,
identity/compliance review, protected role definitions, system health, and audit history. Admin changes are
stored in the same local SQLite service used by the payment workflow.

The Operations & Reliability module adds durable player/admin notifications,
read-only cross-ledger reconciliation, auditable incident handling, live engine
health, and verified private recovery archives. Backup restore remains an
offline maintenance procedure rather than a browser action. See
`docs/operations-architecture.md` for the invariants and production boundary.

The Support & Disputes module adds trackable player cases for payments, bets,
streams, accounts, verification, and responsible play. It includes reference
ownership checks, priority-based SLA deadlines, staff assignment, public
replies, player-safe private notes, resolution history, notifications, and
auditing. Players can open, follow, reply to, and reopen resolved cases from
their profile. See `docs/support-architecture.md` for lifecycle and visibility
invariants.

The Risk & Finance module adds consolidated financial position, fourteen-day
movement, payment and betting exposure, protected CSV evidence exports, and an
idempotent anomaly-detection queue. Large withdrawals, rapid cash-out,
rejections, betting velocity, and shared beneficiaries are surfaced for human
review. Detection never changes a wallet or account automatically. See
`docs/intelligence-architecture.md` for calculations, rules, and safeguards.

The console uses named administrator accounts rather than a shared browser key.
Roles are enforced on every server request, staff can enable authenticator MFA
with one-use recovery codes, and audit records include the actor, role, request
identifier, and connected address. Local `--preview` mode keeps its
loopback-only zero-login shortcut for interface review.

Every display asset can be supplied in the administrator UI either as a local
upload or as a secure link. This includes match thumbnails, recorded match
videos/stream sources, banners, the site logo, and payment QR artwork. Uploaded
images support PNG, JPEG, and WebP up to 5 MB; uploaded playback supports MP4
and WebM up to 250 MB with byte-range delivery for browser seeking.

## Cockfight engine foundation

The local service now includes authoritative match scheduling, versioned odds,
short-lived bet quotes, risk checks, wallet holds, idempotent bet placement,
result declaration, and transactional settlement. The player uses these APIs
directly; it no longer creates pretend local tickets. A lightweight polling
loop refreshes canonical match, account, and stream state across every supported
hosting environment. The admin console exposes
the legal match-state transitions, market suspension and repricing, risk-policy
controls, official results, settlement, audit history, and engine health.

Recorded MP4/WebM playback can be scheduled as live. The player calculates the
video position from the server's actual start time, so viewers joining later see
the correct point in the recording instead of starting at zero. See
`docs/engine-architecture.md` for invariants and API boundaries.

The streaming control plane now provides durable camera/mobile sessions,
one-time device pairing, rotated publisher credentials, WHIP publish tickets,
WHEP/HLS playback routing, health samples, degraded/offline detection, operator
stop controls, and ordered stream events. The `/broadcast/` studio supports
camera selection, quality controls, health reporting, and mobile pairing. A
real SRS media plane must be configured before its Go live button can publish;
the deployment template is in `deploy/streaming/`.

### China 24/7 auto-match feed

`server/china_feed_engine.py` mirrors the continuous upstream cockfight service
into the same engine. When enabled from **Admin → Games & Live → China 24/7
auto-match**, a background poller reads the upstream match-info endpoint every
few seconds and:

- creates one `admin_games` row per upstream fight (`source=CHINA_FEED`, with
  `external_ref` and `match_number`), featured on the player home by default;
- opens the market while upstream `allowBetting` is true and suspends it (and
  moves the match to LIVE) as soon as upstream closes betting, so quotes, wallet
  holds, and risk checks behave exactly like a manually operated match;
- declares and settles results from `winTeam` (1 Meron→RED, 2 Wala→BLUE,
  3 Tie→DRAW, 4→CANCELLED with refunds) through `CockfightEngine`, so ledgers,
  bet history, and notifications are the authoritative ones;
- recovers any missed result from the upstream history endpoint and, after a
  configurable run of upstream failures, suspends the open market instead of
  leaving it accepting bets on a dead feed;
- streams the upstream `liveUrl` (or an operator override) through an `IFRAME`
  stream type; the CSP `frame-src` is extended to that origin automatically.

Odds for feed matches are the fixed values configured on the feed panel and can
still be repriced per match through the odds engine. `/api/cockfight/china/current/`
exposes the feed state to the player; `/api/admin/china-feed/` (GET/POST),
`/poll/`, and `/recover/` drive it from the console. Tests: `tests/china-feed.py`.

## Identity and access engine

Player registration verifies Indian mobile numbers with a five-minute,
single-use OTP challenge. Passwords are stored only as salted adaptive hashes;
registration challenges never retain plaintext passwords. Password recovery
revokes existing sessions before a new login. User and administrator browsers
use opaque server-side sessions in HttpOnly, SameSite cookies with a separate
session-bound CSRF token. Login and OTP failures are attempt-limited and locked
accounts cannot access wallets, bets, or payments.

For a non-preview start, configure the first owner account once:

```text
ROOSTERRUN_BOOTSTRAP_ADMIN_USERNAME=owner
ROOSTERRUN_BOOTSTRAP_ADMIN_PASSWORD=<a strong unique password>
ROOSTERRUN_BOOTSTRAP_ADMIN_NAME=Platform Owner
```

Production mobile verification also requires `ROOSTERRUN_SMS_WEBHOOK_URL` and,
when the provider requires it, `ROOSTERRUN_SMS_WEBHOOK_TOKEN`. Never enable
`ROOSTERRUN_OTP_TEST_MODE` outside isolated automated tests.

## Operating modes

`REAL_MONEY` is the default operating mode: wallets, deposits, withdrawals, betting, and settlement all move real funds and new users start at ₹0. Player identity (KYC) review is disabled by default; administrators can require it per action from the compliance policy.

Set `ROOSTERRUN_OPERATING_MODE=APPROVAL_DEMO` on an authenticated deployment to present registration, identity review, demo betting, settlement, manual deposit review, and manual withdrawal review end to end. New users receive the amount configured by `ROOSTERRUN_DEMO_STARTING_BALANCE` as non-cash demo credits.

The player and administrator interfaces label this mode, payment dialogs warn testers not to send real money, and the server rejects every unsupported operating-mode value. Use a separate database and storage volume for approval demonstrations; never promote its balances, screenshots, UTRs, or transaction history into a future live environment.

## Production container stack

`deploy/production/` packages the application, SRS WHIP/WHEP/HLS/DVR media
plane, Caddy HTTPS, managed-PostgreSQL connectivity and pooling, encrypted
off-host restic backups, restore-drill evidence, Prometheus/Alertmanager,
Blackbox probes, Loki/Promtail logs, and Grafana. Follow its README and replace
every example value. `/health/live/` reports process liveness;
`/health/ready/` stays at 503 until PostgreSQL TLS, storage, an administrator,
SMS identity, secret rotation, external alerts, a reachable media plane,
recent off-site backup/restore evidence, secure cookies, and workers are ready.

## Compliance and responsible-play engine

The player profile now includes private identity/age submission and fully
server-enforced daily deposit and stake limits, cooling-off, and fixed-term or
permanent self-exclusion. Limit decreases apply immediately; increases wait for
the configured delay. Restrictions block deposits and betting while keeping
withdrawals and support available.

The admin Compliance module provides an identity review queue, protected
document viewing, approve/reject/more-information decisions, jurisdiction
configuration, verification policy, and audit history. Identity files are
stored under `var/manual_payments/private/identity/`, outside the public upload
tree. Aadhaar images are deliberately rejected; any future Aadhaar integration
must use UIDAI's secure offline verification flow.

Local preview always runs as `SOCIAL_PREVIEW` with demo credits. Real-money
operation is enabled only through the `ROOSTERRUN_OPERATING_MODE=REAL_MONEY`
deployment environment variable; the admin dashboard cannot switch it. See `docs/compliance-architecture.md` for enforcement
rules and the legal-release boundary.

## Manual Indian payments preview

The repository uses SQLite for zero-setup local testing and PostgreSQL for the
production approval stack. It supports admin-managed UPI/bank accounts and QR images, deposit UTR
and screenshot submission, withdrawal beneficiary details, admin approval or
rejection, payout UTR/proof, pending balance holds, and an immutable wallet
ledger.

Start the payment-enabled preview with:

```sh
npm run preview
```

Payment records and uploads are stored under `var/manual_payments/` and are
excluded from source control. Payment administration is available at `/admin/#payments`
while preview mode is active. See `docs/manual-payments.md` for the workflow and
production integration contract.

## External launch prerequisites

The repository now contains adapters and deployment definitions for each
runtime dependency, but a public launch still requires real operator-owned
accounts and live-environment evidence that cannot be embedded in source
control: domain/DNS, managed PostgreSQL, SMS/SMTP/alert credentials, private
object storage, and a separate restore target. Real-money use
also requires independent legal, privacy, payments, licensing, and animal-welfare
approval for every intended jurisdiction. Operators are responsible for completing that
review before running a `REAL_MONEY` deployment.

## Local frontend review

Run `npm run preview` and open `/play/`. This serves the frontend and the local
payment and cockfight engine APIs together. The admin console is available at
`/admin/` in the same preview process.

## Checks

Node.js and Python are required for the regression, load, concurrency,
provider-outbox, recovery, and approval-demo checks:

```sh
npm test
```

## Production warning

Do not deploy this repository for real-money use. The current India operating
mode intentionally rejects production deposits and bets. Security, settlement,
identity processing, payment handling, animal-welfare obligations, and every
intended jurisdiction must be independently reviewed before any release.
