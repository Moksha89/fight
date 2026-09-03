#!/usr/bin/env bash
set -euo pipefail
: "${RESTIC_REPOSITORY:?Set RESTIC_REPOSITORY to encrypted off-host storage}"
: "${RESTIC_PASSWORD_FILE:?Set RESTIC_PASSWORD_FILE}"
staging="$(mktemp -d)"
trap 'rm -rf -- "$staging"' EXIT
if ! restic snapshots >/dev/null 2>&1; then restic init; fi
pg_dump --dbname "${ROOSTERRUN_DATABASE_URL:?Set ROOSTERRUN_DATABASE_URL}" --format custom --no-owner --file "$staging/roosterrun.dump"
pg_restore --list "$staging/roosterrun.dump" >/dev/null
sources=("$staging/roosterrun.dump")
for path in /data/uploads /data/private /media-data/recordings; do
  if [ -e "$path" ]; then sources+=("$path"); fi
done
restic backup "${sources[@]}" --exclude /data/private/backups
restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 12 --prune
mkdir -p /restore-state
printf '{"completed_at":"%s","repository":"configured"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /restore-state/last-backup-success.json.tmp
mv /restore-state/last-backup-success.json.tmp /restore-state/last-backup-success.json
