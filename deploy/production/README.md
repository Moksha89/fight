# Production approval-demo runtime

This deployment runs the approval-demo application, SRS WHIP/WHEP/HLS/DVR,
Caddy HTTPS, encrypted off-host backups, Prometheus, Alertmanager, Blackbox,
Loki, Promtail, and Grafana. It expects a managed PostgreSQL primary/cluster
endpoint; SQLite is rejected by the default production readiness policy.

## 1. External services

Prepare these before starting the stack:

- a domain whose A record points to the host;
- managed PostgreSQL with automated replication/failover and TLS;
- a separate empty PostgreSQL database whose name contains `restore` or
  `drill` for destructive restore testing;
- an S3-compatible private bucket (DigitalOcean Spaces is supported by
  restic's S3 backend);
- an HTTPS SMS webhook or Twilio account;
- an SMTP account;
- an HTTPS operations-alert webhook and/or real alert recipients.

Allow TCP 80/443 and UDP 8000. Grafana binds only to `127.0.0.1:3000`; reach it
through an SSH tunnel instead of exposing it publicly.

## 2. Environment and secret files

From the repository root:

```sh
cp .env.example deploy/production/.env
python scripts/rotate_secrets.py --output-dir deploy/production/secrets --generation 1
```

Edit `.env` with the real domain, public server IP, provider settings, backup
repository, and the current rotation timestamp. Place these operator-owned
values in files under `deploy/production/secrets/`:

- `database_url` — managed PostgreSQL DSN ending in `?sslmode=require` (or
  `verify-full`);
- `restore_database_url` — isolated restore target DSN; database name must
  contain `restore` or `drill`;
- `sms_webhook_token`, `smtp_password`, `alert_webhook_token`;
- `aws_access_key_id`, `aws_secret_access_key`.

The generation script creates internal credentials and mode `0600` files.
Never commit `.env` or `secrets/`. During rotation, the prior SRS hook key is
retained for one generation so existing callbacks remain valid while SRS and
the app restart. Remove the bootstrap administrator password from the runtime
after the owner is created, MFA is enabled, and an emergency Super Admin has
been tested.

## 3. Optional SQLite migration

Stop the old application and make a verified copy of its SQLite file. The
migration refuses any non-empty PostgreSQL schema, migrates inside one
transaction, advances sequences, compares every table row count, and prints
the source SHA-256:

```sh
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite var/manual_payments/payments.sqlite3 \
  --postgres-url-file deploy/production/secrets/database_url \
  --dry-run
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite var/manual_payments/payments.sqlite3 \
  --postgres-url-file deploy/production/secrets/database_url
```

Do not migrate approval-demo balances or uploaded evidence into a future
licensed environment.

## 4. Start, verify, and restore-test

```sh
cd deploy/production
docker compose config
docker compose up -d --build
docker compose ps
```

The app initially stays `not_ready` until an off-host backup and isolated
restore drill succeed. The backup worker runs immediately and then every six
hours. After its first success:

```sh
docker compose run --rm --entrypoint /usr/local/bin/restore-drill.sh backup
docker compose restart app
curl -fsS https://YOUR_DOMAIN/health/ready/
```

The restore script refuses targets whose URL does not contain `restore` or
`drill`. It restores the latest encrypted restic snapshot, validates the dump,
performs a clean restore only into that isolated target, checks required
tables, and writes the readiness marker. A successful backup marker expires
after two days; the restore-drill marker expires after 90 days.

## 5. Provider and media verification

Run dependency checks inside the app container. Adding the optional recipient
arguments sends clearly labelled verification messages:

```sh
docker compose exec app python scripts/production_smoke.py
docker compose exec app python scripts/production_smoke.py \
  --send-sms-to +91XXXXXXXXXX \
  --send-email-to operator@example.com \
  --send-alert
```

Create a match broadcast in the admin Games & Live module, pair a real phone,
publish over WHIP for at least one DVR segment, disconnect/reconnect the phone,
and verify WHEP playback, HLS fallback, and the recording URL in the stream
session. SRS health is probed every five seconds and is part of readiness.

## 6. Monitoring

Prometheus scrapes application metrics and a readiness probe. Alertmanager
posts firing and resolved alerts to the authenticated internal application
hook; the durable delivery worker fans critical alerts out to configured SMS,
email, and webhook destinations with exponential retries. Promtail sends
structured application, proxy, media, and database container logs to Loki.
Grafana is pre-provisioned with Prometheus and Loki data sources.

Use an independent external uptime monitor against
`https://YOUR_DOMAIN/health/live/` as well; a monitor on the same host cannot
detect total host or network failure.

## Operating boundary

Set `ROOSTERRUN_OPERATING_MODE=REAL_MONEY` for live wallets. `APPROVAL_DEMO`
runs the same flows with non-cash demo credits.
