#!/usr/bin/env bash
###############################################################################
# scripts/restore-db.sh <backup.sql.gz>
###############################################################################
set -euo pipefail

cd "$(dirname "$0")/.."
BACKUP="${1:?Usage: restore-db.sh <backup.sql.gz>}"

if [[ ! -f "${BACKUP}" ]]; then
  echo "File not found: ${BACKUP}" >&2
  exit 1
fi
set -a; source .env.production; set +a

echo "!! This will OVERWRITE the database '${POSTGRES_DB:-linkforge}'."
read -p "Type 'restore' to continue: " ack
[[ "${ack}" == "restore" ]] || { echo "Aborted."; exit 1; }

gunzip -c "${BACKUP}" | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "${POSTGRES_USER:-linkforge}" -d "${POSTGRES_DB:-linkforge}"

echo "==> Restored from ${BACKUP}"
