#!/usr/bin/env bash
###############################################################################
# scripts/backup-db.sh
#
# Dumps the Linkforge Postgres database, gzips the result and keeps the last
# RETENTION_DAYS backups locally.  Optionally uploads to S3 if AWS_S3_BUCKET
# is set (uses awscli, expected to be present on the VPS).
###############################################################################
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env.production ]]; then
  echo ".env.production missing." >&2
  exit 1
fi
set -a; source .env.production; set +a

BACKUP_DIR="${BACKUP_DIR:-/srv/linkforge/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="${BACKUP_DIR}/linkforge-${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "==> Dumping to ${FILE}"
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump --no-owner --no-acl --clean --if-exists -U "${POSTGRES_USER:-linkforge}" "${POSTGRES_DB:-linkforge}" \
  | gzip -9 > "${FILE}"

echo "==> Pruning backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -type f -name 'linkforge-*.sql.gz' -mtime +${RETENTION_DAYS} -delete

if [[ -n "${AWS_S3_BUCKET:-}" ]]; then
  echo "==> Uploading to s3://${AWS_S3_BUCKET}/backups/"
  aws s3 cp "${FILE}" "s3://${AWS_S3_BUCKET}/backups/$(basename "${FILE}")"
fi

echo "==> Backup done: $(ls -lh "${FILE}")"
