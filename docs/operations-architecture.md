# Operations and reliability architecture

RoosterRun's operations layer is implemented by `server/operations_engine.py`
and exposed to authorised staff at `/admin/#operations`. It uses the same
transaction boundary as payments, betting, settlement, authentication, and
compliance so operational messages cannot get ahead of committed state. Local
preview uses SQLite; production uses pooled TLS PostgreSQL connections.

## Notification delivery

Player and administrator messages are durable records with deterministic
deduplication keys. In-app delivery is always active. Production SMS supports
a generic HTTPS provider contract or Twilio, email uses authenticated SMTP with
TLS, and critical operations alerts can fan out to SMS, email, and an HTTPS
webhook. External attempts are stored in `notification_deliveries`, claimed
transactionally, retried with exponential backoff, and marked failed only after
the attempt budget is exhausted.

The player bell loads the authoritative feed and supports individual or bulk
read acknowledgement. External delivery never replaces the in-app record.

## Financial reconciliation

Reconciliation is read-only with respect to wallets, payment requests, bets,
and ledgers. Each run checks:

1. Approved payment requests have exactly one wallet ledger entry.
2. Pending or rejected payments have no wallet mutation.
3. Approved payment amounts have the correct deposit/withdrawal sign.
4. Pending bets have exactly one active hold for the accepted stake.
5. Terminal bets have no active hold.
6. Settled tickets have one unique account-ledger settlement.
7. Player available balances do not become negative.
8. The configured database remains queryable.

Findings are immutable evidence attached to a run. Critical findings create or
refresh a durable incident. A later clean run closes only reconciliation
incidents whose exact condition has cleared; it never changes financial data.

## Incident management

Incidents have a stable reference, source fingerprint, severity, occurrence
counter, and open/acknowledged/resolved lifecycle. Acknowledgement and
resolution are server-authorised and audited. Resolution requires an operator
note. Backup, delivery, media, uptime, and reconciliation failures are surfaced
through the same workflow.

## Recovery

An authorised operator can create a protected recovery archive containing an
online SQLite backup or PostgreSQL custom-format dump, uploads, private payment
evidence, private identity documents, and a manifest. Database integrity,
archive contents, file size, and SHA-256 are verified before completion.

The independent production backup worker makes a PostgreSQL dump and sends it,
application files, private evidence, and SRS recordings to an encrypted restic
repository. Retention keeps 14 daily, 8 weekly, and 12 monthly recovery points.
The restore drill only targets a database URL containing `restore` or `drill`.
Production readiness requires a backup newer than two days and a restore drill
newer than 90 days.

Restore is not exposed in the browser. Cutover to a restored database remains
a separately controlled maintenance operation.

## Metrics and logs

Prometheus records HTTP latency/errors and engine gauges. Blackbox probes
readiness, Alertmanager feeds the authenticated notification outbox, and
Promtail centralises structured container logs in Loki. Grafana uses both data
sources. An independent monitor outside the host is still required to detect a
complete host or network failure.

The supported public runtime remains approval-demo mode with non-cash credits;
these controls do not enable real-money operation.
