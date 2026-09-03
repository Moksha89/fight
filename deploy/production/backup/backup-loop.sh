#!/usr/bin/env bash
set -euo pipefail
export AWS_ACCESS_KEY_ID="$(cat "${AWS_ACCESS_KEY_ID_FILE:?Set AWS_ACCESS_KEY_ID_FILE}")"
export AWS_SECRET_ACCESS_KEY="$(cat "${AWS_SECRET_ACCESS_KEY_FILE:?Set AWS_SECRET_ACCESS_KEY_FILE}")"
export ROOSTERRUN_DATABASE_URL="$(cat "${ROOSTERRUN_DATABASE_URL_FILE:?Set ROOSTERRUN_DATABASE_URL_FILE}")"
interval="${ROOSTERRUN_BACKUP_INTERVAL_SECONDS:-21600}"
while true; do
  /usr/local/bin/backup-once.sh || true
  sleep "$interval"
done
