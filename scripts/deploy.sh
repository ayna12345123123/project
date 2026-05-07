#!/usr/bin/env bash
###############################################################################
# scripts/deploy.sh
#
# Pull the latest code, build the Docker image, run database migrations and
# zero-downtime restart the app + worker.  Designed to be run as the deploy
# user (nurbek) on the VPS.
#
# Usage (locally):
#   ssh -p 2222 nurbek@164.92.240.90 'cd /srv/linkforge && ./scripts/deploy.sh'
###############################################################################
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env.production ]]; then
  echo ".env.production missing; create it from .env.example first." >&2
  exit 1
fi
set -a; source .env.production; set +a

echo "==> Pulling latest"
git fetch --all --prune
git checkout "${DEPLOY_REF:-main}"
git pull --ff-only

echo "==> Building image"
docker compose -f docker-compose.prod.yml build app

echo "==> Running database migrations"
docker compose -f docker-compose.prod.yml run --rm app \
  node node_modules/prisma/build/index.js migrate deploy

echo "==> Rolling restart"
docker compose -f docker-compose.prod.yml up -d --no-deps --build app worker
docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload || true

echo "==> Pruning old images"
docker image prune -f

echo "==> Deploy done.  Health check:"
curl -fsS https://together.kebruni.me/api/health || true
