# Linkforge — Production deployment guide

Target host:

| Field           | Value                       |
| --------------- | --------------------------- |
| Domain          | `together.kebruni.me`       |
| VPS IP          | `164.92.240.90`             |
| SSH port        | `2222`                      |
| Deploy user     | `nurbek` (sudo, key-based)  |
| OS              | Ubuntu 24.04 LTS            |
| Container stack | Docker + Docker Compose v2  |

> ⚠️ **Never** commit secrets. Real credentials are configured via:
>
> - GitHub Actions secrets (`DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_USER`,
>   `DEPLOY_SSH_KEY`, `LETSENCRYPT_EMAIL`, all `*_SECRET` and `*_KEY` envs).
> - `/home/nurbek/linkforge/.env.production` on the VPS, owned by `nurbek`,
>   `chmod 600`. This file is **not** in git.
> - `docker compose` reads it via `env_file:`.

---

## 1. DNS

Set the following records on the registrar of `kebruni.me` (e.g. Cloudflare):

| Type | Name      | Value           | Proxy   | TTL   |
| ---- | --------- | --------------- | ------- | ----- |
| A    | `together`| `164.92.240.90` | DNS only | Auto |

Wildcard for future custom-domain feature (out of MVP):

| Type | Name      | Value           |
| ---- | --------- | --------------- |
| A    | `*.together` | `164.92.240.90` |

After saving, verify with `dig +short together.kebruni.me`.

---

## 2. First-time VPS bootstrap (run as `root` over the existing SSH access)

```bash
# 1) Connect (replace key path / port as configured)
ssh -p 2222 root@164.92.240.90

# 2) Update + install base tools
apt-get update && apt-get -y upgrade
apt-get install -y curl git ufw fail2ban unattended-upgrades \
    ca-certificates gnupg lsb-release software-properties-common \
    jq htop tmux

# 3) Create deploy user (skip if `nurbek` already exists)
adduser --disabled-password --gecos "" nurbek
usermod -aG sudo nurbek
mkdir -p /home/nurbek/.ssh && chmod 700 /home/nurbek/.ssh

# 4) Authorise your public key for nurbek
#    From your laptop:
#      cat ~/.ssh/id_ed25519.pub | ssh -p 2222 root@164.92.240.90 \
#        'cat >> /home/nurbek/.ssh/authorized_keys'
chown -R nurbek:nurbek /home/nurbek/.ssh
chmod 600 /home/nurbek/.ssh/authorized_keys

# 5) Harden SSH
sed -i \
    -e 's/^#\?Port .*/Port 2222/' \
    -e 's/^#\?PermitRootLogin .*/PermitRootLogin prohibit-password/' \
    -e 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' \
    -e 's/^#\?KbdInteractiveAuthentication .*/KbdInteractiveAuthentication no/' \
    -e 's/^#\?ChallengeResponseAuthentication .*/ChallengeResponseAuthentication no/' \
    /etc/ssh/sshd_config
systemctl restart ssh

# 6) Firewall (UFW)
ufw default deny incoming
ufw default allow outgoing
ufw allow 2222/tcp comment 'SSH'
ufw allow 80/tcp   comment 'HTTP'
ufw allow 443/tcp  comment 'HTTPS'
ufw --force enable

# 7) fail2ban — protect SSH
cat >/etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled  = true
port     = 2222
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
systemctl restart fail2ban

# 8) Automatic security updates
dpkg-reconfigure --priority=low unattended-upgrades

# 9) Install Docker Engine + Compose plugin
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker nurbek
systemctl enable --now docker

# 10) Disk locations
install -d -o nurbek -g nurbek /home/nurbek/linkforge
install -d -o nurbek -g nurbek /home/nurbek/linkforge/data/postgres
install -d -o nurbek -g nurbek /home/nurbek/linkforge/data/redis
install -d -o nurbek -g nurbek /home/nurbek/linkforge/data/letsencrypt
install -d -o nurbek -g nurbek /home/nurbek/linkforge/backups
```

The `scripts/setup-vps.sh` in this repo packages steps 2-10 idempotently so
they can be re-run safely.

---

## 3. First deploy

From now on we work as `nurbek`:

```bash
ssh -p 2222 nurbek@164.92.240.90
cd /home/nurbek/linkforge

# 1) Clone the repo (read-only deploy key recommended; HTTPS+PAT works too)
git clone https://github.com/<owner>/<repo>.git app
cd app

# 2) Create the production env file
cp .env.example .env.production
chmod 600 .env.production
$EDITOR .env.production   # fill in DATABASE_URL, AUTH_SECRET, OAuth keys etc.

# 3) Build and start everything
docker compose -f docker-compose.prod.yml --env-file .env.production \
    up -d --build

# 4) Run database migrations (one-shot)
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec web pnpm prisma migrate deploy

# 5) Optional seed (themes, reserved slugs, default templates)
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec web pnpm prisma db seed
```

`docker-compose.prod.yml` brings up:

- `web` – Next.js (port 3000, internal only)
- `worker` – BullMQ workers
- `postgres` – Postgres 16 (volume `data/postgres`)
- `redis` – Redis 7 (volume `data/redis`, persistent AOF)
- `nginx` – reverse proxy, terminating TLS, exposed on `:80` and `:443`
- `certbot` – Let's Encrypt, runs in `--webroot` mode through nginx

---

## 4. SSL — first issuance and auto-renewal

```bash
# Bootstrap the cert. Initially nginx serves a temporary HTTP-only config
# that just exposes /.well-known/acme-challenge.
bash scripts/ssl-init.sh together.kebruni.me admin@kebruni.me

# After success, nginx reloads with the full HTTPS config (HTTP/2,
# strict TLS, HSTS) and certbot installs a renew timer.
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec nginx nginx -t && \
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec nginx nginx -s reload
```

Renewal is automatic (twice-daily certbot run inside the `certbot` container).
The `nginx` container picks up new certs via `inotifywait` reload.

Verify TLS:

```bash
curl -I https://together.kebruni.me           # 200 + HSTS header
curl -I http://together.kebruni.me            # 301 → https://...
openssl s_client -connect together.kebruni.me:443 -servername together.kebruni.me \
    < /dev/null | openssl x509 -noout -dates
```

---

## 5. CI/CD (GitHub Actions)

`.github/workflows/ci.yml` runs on every PR and push to `main`:

1. `pnpm install --frozen-lockfile`
2. `pnpm lint`
3. `pnpm typecheck`
4. `pnpm test`
5. `pnpm build`

`.github/workflows/deploy.yml` runs on push to `main` after CI is green:

1. Checkout + login to the registry (we publish a private image to GHCR).
2. `docker buildx build --push` for `web` and `worker` images, tagged
   `:sha-<short>` and `:latest`.
3. SSH into the VPS (using `DEPLOY_SSH_KEY` stored as a GitHub secret), then:

   ```bash
   cd /home/nurbek/linkforge/app
   git fetch --all --prune
   git reset --hard origin/main          # always deploys what CI built
   docker compose -f docker-compose.prod.yml --env-file .env.production \
       pull web worker
   docker compose -f docker-compose.prod.yml --env-file .env.production \
       up -d --no-deps --build web worker
   docker compose -f docker-compose.prod.yml --env-file .env.production \
       exec -T web pnpm prisma migrate deploy
   ```

   `up -d --no-deps web worker` performs a **zero-downtime rolling restart**:
   the new container starts and passes its health-check before the old one is
   torn down, and Nginx continues to serve the old one in the meantime.

4. On failure the workflow rolls back by retagging `:latest` to the previous
   image and re-running `up -d --no-deps`.

Required GitHub Actions secrets:

| Name                   | Used in                                             |
| ---------------------- | --------------------------------------------------- |
| `DEPLOY_HOST`          | `164.92.240.90`                                     |
| `DEPLOY_PORT`          | `2222`                                              |
| `DEPLOY_USER`          | `nurbek`                                            |
| `DEPLOY_SSH_KEY`       | private key matching `nurbek`'s `authorized_keys`   |
| `GHCR_TOKEN`           | PAT with `write:packages` if pushing images to GHCR |
| `LETSENCRYPT_EMAIL`    | for first-time SSL bootstrap                        |
| `AUTH_SECRET`, `STRIPE_*`, `OPENAI_API_KEY`, …    | injected into `.env.production` via the workflow if you prefer to manage them centrally |

---

## 6. Backups

`scripts/backup-postgres.sh` is run nightly from cron on the host:

```cron
# crontab -e   (as nurbek)
0 3 * * *  /home/nurbek/linkforge/app/scripts/backup-postgres.sh
```

It performs:

1. `docker compose exec -T postgres pg_dump -Fc -U linkforge linkforge`
   piped to a timestamped file under `/home/nurbek/linkforge/backups/`.
2. Removes backups older than 14 days.
3. Optionally `aws s3 cp` (or `rclone copy`) the dump to a remote bucket if
   `BACKUP_REMOTE` is set in `.env.production`.

Restore:

```bash
bash scripts/restore-postgres.sh /home/nurbek/linkforge/backups/2026-05-07.dump
```

---

## 7. Day-2 operations

### Logs

```bash
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml logs -f nginx
journalctl -u docker -f
fail2ban-client status sshd
```

### Health checks

- `https://together.kebruni.me/api/health` — JSON `{ ok, db, redis }`.
- Add an external uptime probe to alert when this returns non-200.

### Shell into containers

```bash
docker compose -f docker-compose.prod.yml exec web sh
docker compose -f docker-compose.prod.yml exec postgres psql -U linkforge
docker compose -f docker-compose.prod.yml exec redis redis-cli
```

### Migrations

```bash
docker compose -f docker-compose.prod.yml exec web pnpm prisma migrate deploy
```

Never run `prisma migrate dev` against production — only `migrate deploy`.

### Manual rollback

```bash
cd /home/nurbek/linkforge/app
git fetch --all
git reset --hard <previous-good-sha>
docker compose -f docker-compose.prod.yml --env-file .env.production \
    up -d --no-deps --build web worker
```

If you need to rollback Postgres schema, restore from backup (see §6).

### Reload Nginx without downtime

```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -t \
 && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## 8. Hardening checklist

- [x] SSH on non-default port (2222), key-only, root login restricted.
- [x] UFW blocks everything except 2222/80/443 outbound-allow.
- [x] fail2ban watches sshd and (optionally) nginx auth zones.
- [x] Unattended-upgrades enabled.
- [x] Docker daemon runs without exposing the API socket; containers run
      as a non-root user; capabilities dropped where possible.
- [x] Postgres bound only to the docker network.
- [x] Redis bound only to the docker network, password-protected
      (`REDIS_PASSWORD` in env, propagated to `REDIS_URL`).
- [x] `.env.production` `chmod 600`, owned by `nurbek` only.
- [x] Backups encrypted at rest if shipped off-host (`age`/`gpg`).
- [x] HSTS preloaded after a few weeks of green deploys.

---

## 9. Scaling beyond a single VPS

When the single-host setup becomes insufficient:

1. Move Postgres to a managed service (Neon, RDS, Cloud SQL). Update
   `DATABASE_URL` only — Prisma is unchanged.
2. Move Redis to Upstash / Redis Cloud / ElastiCache. Update `REDIS_URL`.
3. Add a second VPS, deploy `web` + `worker` to both, point Nginx (or move
   to a CDN like Cloudflare / Bunny) at both as upstreams. The same image
   runs on every node — no code change.
4. Once you have ≥3 nodes, switch to k3s/k8s using the existing Dockerfile;
   a starter Helm chart is on the roadmap (v1.3).
5. Put a CDN in front of `/u/:slug` and `_next/static`. The Nginx `Cache-
   Control` headers are already correct.

---

## 10. Quick reference — common commands

```bash
# Open SSH
ssh -p 2222 nurbek@164.92.240.90

# Update to latest main and redeploy
cd /home/nurbek/linkforge/app && \
  git pull --ff-only && \
  docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build && \
  docker compose -f docker-compose.prod.yml --env-file .env.production exec -T web pnpm prisma migrate deploy

# Tail web logs
docker compose -f docker-compose.prod.yml logs -f web

# Get into a Postgres shell
docker compose -f docker-compose.prod.yml exec postgres psql -U linkforge

# Backup now
bash /home/nurbek/linkforge/app/scripts/backup-postgres.sh

# Restart Nginx after editing config
docker compose -f docker-compose.prod.yml exec nginx nginx -t && \
  docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```
