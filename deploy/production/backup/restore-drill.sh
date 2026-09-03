#!/usr/bin/env bash
set -euo pipefail
export AWS_ACCESS_KEY_ID="$(cat "${AWS_ACCESS_KEY_ID_FILE:?Set AWS_ACCESS_KEY_ID_FILE}")"
export AWS_SECRET_ACCESS_KEY="$(cat "${AWS_SECRET_ACCESS_KEY_FILE:?Set AWS_SECRET_ACCESS_KEY_FILE}")"
if [ -n "${ROOSTERRUN_RESTORE_TEST_DATABASE_URL_FILE:-}" ]; then
  export ROOSTERRUN_RESTORE_TEST_DATABASE_URL="$(cat "$ROOSTERRUN_RESTORE_TEST_DATABASE_URL_FILE")"
fi
: "${ROOSTERRUN_RESTORE_TEST_DATABASE_URL:?Use an isolated restore/drill database URL}"
case "$ROOSTERRUN_RESTORE_TEST_DATABASE_URL" in
  *restore*|*drill*) ;;
  *) echo "Restore target must contain 'restore' or 'drill'." >&2; exit 2 ;;
esac
target="$(mktemp -d)"
trap 'rm -rf -- "$target"' EXIT
restic restore latest --target "$target"
dump="$(find "$target" -name roosterrun.dump -type f -print -quit)"
test -n "$dump"
pg_restore --list "$dump" >/dev/null
pg_restore --clean --if-exists --no-owner --dbname "$ROOSTERRUN_RESTORE_TEST_DATABASE_URL" "$dump"
psql "$ROOSTERRUN_RESTORE_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "SELECT COUNT(*) AS required_tables FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('user_wallets','payment_requests','cockfight_bets','stream_sessions','admin_audit_log');"
mkdir -p /restore-state
printf '{"completed_at":"%s","target":"isolated"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /restore-state/last-restore-drill.json.tmp
mv /restore-state/last-restore-drill.json.tmp /restore-state/last-restore-drill.json
echo "Restore drill completed against the isolated target."
