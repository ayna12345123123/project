#!/usr/bin/env bash
###############################################################################
# scripts/ssl-init.sh
#
# Issue the very first Let's Encrypt certificate.  Subsequent renewals are
# handled by the certbot container in docker-compose.prod.yml.
#
# Usage:
#   DOMAIN=together.kebruni.me EMAIL=admin@kebruni.me ./scripts/ssl-init.sh
###############################################################################
set -euo pipefail

DOMAIN="${DOMAIN:-together.kebruni.me}"
EMAIL="${EMAIL:?EMAIL env var is required}"
COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"

mkdir -p ./letsencrypt/conf ./letsencrypt/www

echo "==> Bringing up nginx with HTTP-only config (no certs yet)"

# Temporary http-only config so nginx starts before we have the cert
HTTP_ONLY=./nginx/conf.d/_init.conf
cat > "${HTTP_ONLY}" <<NGINX
server {
    listen 80 default_server;
    server_name ${DOMAIN};
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 200 'init';
        add_header Content-Type text/plain;
    }
}
NGINX

# Move the production conf out of the way until cert exists
PROD_CONF=./nginx/conf.d/${DOMAIN}.conf
PROD_CONF_DISABLED=${PROD_CONF}.disabled
if [[ -f "${PROD_CONF}" ]]; then
  mv "${PROD_CONF}" "${PROD_CONF_DISABLED}"
fi

${COMPOSE} up -d nginx

echo "==> Requesting certificate for ${DOMAIN}"
${COMPOSE} run --rm certbot certonly \
  --webroot --webroot-path=/var/www/certbot \
  --email "${EMAIL}" --agree-tos --no-eff-email \
  -d "${DOMAIN}"

echo "==> Restoring production nginx config"
rm -f "${HTTP_ONLY}"
if [[ -f "${PROD_CONF_DISABLED}" ]]; then
  mv "${PROD_CONF_DISABLED}" "${PROD_CONF}"
fi

${COMPOSE} exec nginx nginx -s reload || ${COMPOSE} restart nginx
echo "==> SSL ready for https://${DOMAIN}"
