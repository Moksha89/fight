# RoosterRun cockfight engine architecture

This document describes the authoritative local engine foundation. The browser
is a client of these rules; it never decides whether a wager is accepted or how
a wallet is settled.

## Engine boundaries

| Engine | Current responsibility | Durable records |
| --- | --- | --- |
| Match | Schedule validation, legal lifecycle transitions, actual start and result timestamps | `admin_games`, `engine_match_events` |
| Odds | Immutable market versions and open/suspended state | `odds_snapshots` |
| Risk | Per-ticket limits, user exposure, match pool, outcome liability and request velocity | `risk_decisions`, `platform_config` |
| Betting | Short-lived server quotes and exactly-once ticket creation | `bet_quotes`, `cockfight_bets` |
| Wallet | Available-balance calculation, bet and withdrawal holds, append-only statement | `wallet_holds`, `account_ledger`, `wallet_ledger` |
| Settlement | Idempotent win/loss/refund processing inside one database transaction | `cockfight_bets`, `wallet_holds`, `account_ledger` |
| Realtime | Ordered outbox events for polling now and WebSocket fan-out later | `engine_events` |
| Streaming | Publisher authorization, mobile pairing, playback routing, health and expiry | `stream_sessions`, `stream_health_samples` |
| Payments | Manual Indian deposit and withdrawal review with proof and UTR handling | `payment_requests`, `payment_accounts`, `wallet_ledger` |
| Identity | Mobile OTP registration, recovery, opaque sessions, CSRF, staff RBAC and MFA | `user_accounts`, `admin_accounts`, `auth_challenges`, `auth_sessions`, `admin_mfa_recovery_codes` |

## Match lifecycle

The valid forward path is:

`DRAFT -> SCHEDULED -> BETTING_OPEN -> BETTING_CLOSED -> LIVE -> AWAITING_RESULT -> SETTLED`

Cancellation is supported before settlement. The scheduler advances due matches
using server time. Operators cannot edit status directly, and schedule, outcome
labels, and initial odds are locked after betting opens.

## Betting invariants

1. A quote can be issued only while the match and latest odds market are open.
2. A quote records its exact odds version, stake, potential return and expiry.
3. Risk approval is recorded before a quote is returned.
4. Placing the same quote more than once returns the original ticket.
5. A wallet hold is created in the same transaction as the accepted ticket.
6. Available balance is cash balance minus active bet and withdrawal holds.
7. A suspended or repriced market cannot accept an old unplaced quote.
8. Settlement is repeat-safe: a ticket and its wallet movement are processed once.

## Settlement accounting

- Win: release the stake hold and add only the profit to the cash balance.
- Loss: release the hold and deduct the stake from the cash balance.
- Cancelled match: release the hold with no cash-balance change.
- Every movement receives a unique reference in the append-only account ledger.

This representation keeps the displayed cash balance stable while a wager is
pending and reduces only the available balance. It also lets support staff
reconstruct every wallet change from ledger records.

## Streaming behavior

The player accepts uploaded or linked MP4/WebM video, HLS, YouTube and SRS WHEP
playback sources. Scheduled recorded video is shown as live by seeking to the
elapsed time calculated from `actual_start_at` (or the scheduled start fallback).
Camera/mobile broadcasts are created by an administrator. The same-device studio
receives its publisher credential without placing it in the URL. A different
mobile device pairs once with a 12-character code that expires after ten minutes.
The server stores only hashes of pairing and publisher credentials, issues the
WHIP route after authorization, records WebRTC health, and exposes only the WHEP
or HLS playback route to players. Each WHIP URL also carries a one-use 90-second
media ticket that the SRS `on_publish` hook validates, preventing the public
playback stream name from being reused to publish. SRS hook calls also require a
shared secret configured on both processes. Missing heartbeats mark the
session degraded and then failed. The included `/broadcast/` page is the publishing client; an SRS
media plane configured through the `ROOSTERRUN_*_BASE_URL` environment variables
moves the actual video.

## Main APIs

- `POST /api/user/register/`
- `POST /api/user/login/`
- `POST /api/user/logout/`
- `POST /api/user/forgot-password/request-otp/`
- `POST /api/user/forgot-password/reset/`
- `POST /api/admin/auth/login/`
- `POST /api/admin/auth/mfa/verify/`
- `GET /api/admin/auth/session/`
- `GET|POST /api/admin/team/`
- `POST /api/admin/auth/mfa/enroll/`
- `POST /api/admin/auth/mfa/confirm/`
- `GET /api/cockfight/odds/current/`
- `POST /api/cockfight/bets/quote/`
- `POST /api/cockfight/bets/place-bet/`
- `GET /api/cockfight/bets/`
- `GET /api/user/statement/`
- `GET /api/cockfight/events/?after=<event-id>`
- `POST /api/admin/games/<id>/transition/`
- `POST /api/admin/games/<id>/odds/`
- `POST /api/admin/games/<id>/result/`
- `POST /api/admin/games/<id>/settle/`
- `GET|POST /api/admin/risk/`
- `GET /api/cockfight/engine/health/`
- `GET /api/cockfight/stream/current/`
- `GET /api/cockfight/stream/health/`
- `POST /api/cockfight/broadcast/pair/`
- `POST /api/cockfight/broadcast/sessions/<id>/ticket/`
- `POST /api/cockfight/broadcast/sessions/<id>/heartbeat/`
- `POST /api/cockfight/broadcast/sessions/<id>/stop/`
- `GET /api/admin/streams/`
- `POST /api/admin/games/<id>/broadcast/session/`
- `POST /api/admin/streams/<id>/credentials/`
- `POST /api/admin/streams/<id>/stop/`

## Production hardening gate

Local preview uses WAL SQLite. Production uses pooled TLS PostgreSQL
connections, transaction-scoped advisory locks for the existing serialized
state transitions, idempotency keys, encrypted off-host backups, restore
evidence, KYC/age and jurisdiction checks, responsible-play controls, signed
media publishing tickets, secure sessions, reconciliation, incident handling,
central metrics/logs, and strict health/readiness gates. Canonical state is
refreshed through portable API polling; WebSockets are not required.

`scripts/migrate_sqlite_to_postgres.py` migrates an offline SQLite snapshot only
into an empty PostgreSQL schema and verifies every table row count. A managed
cluster endpoint can support multiple application processes because sessions,
idempotency records, outboxes, holds, and locks are database-coordinated.
Passing tests still does not enable or approve real-money operation.
