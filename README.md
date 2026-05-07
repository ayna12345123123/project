# Linkforge

Production-grade open SaaS platform for link-in-bio / mini-landing pages, in
the spirit of Linktree, Taplink, Beacons and Bento.me — built on Next.js 15,
Prisma, PostgreSQL, Redis and BullMQ.

> **Status:** MVP scaffold. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the
> full system design and [`DEPLOYMENT.md`](./DEPLOYMENT.md) for a step-by-step
> production deploy guide on Ubuntu 24.04 / Docker / Nginx / Let's Encrypt.

## Quick links

- [Architecture & roadmap](./ARCHITECTURE.md)
- [Deployment guide](./DEPLOYMENT.md)
- [Environment variables reference](./.env.example)

## Tech stack

| Layer       | Technology                                                                 |
| ----------- | -------------------------------------------------------------------------- |
| Frontend    | Next.js 15 (App Router, RSC), React 19, TypeScript, Tailwind, shadcn/ui    |
| State       | Zustand (client UI), TanStack Query (server cache), React Hook Form + Zod  |
| Animation   | Framer Motion                                                              |
| Backend     | Next.js Route Handlers + Server Actions, BullMQ workers (`apps/worker`)    |
| Database    | PostgreSQL 16 + Prisma 5                                                   |
| Cache/queue | Redis 7 + BullMQ                                                           |
| Auth        | Auth.js (NextAuth v5), OAuth (Google / GitHub), email magic-link, TOTP 2FA |
| Storage     | S3-compatible (Cloudflare R2 / MinIO)                                      |
| Payments    | Stripe (subscriptions + one-shot digital goods)                            |
| Edge/proxy  | Nginx (HTTP/2, gzip, brotli, rate-limit, security headers)                 |
| TLS         | Let's Encrypt via certbot (auto-renew)                                     |
| CI/CD       | GitHub Actions (lint → typecheck → test → build → deploy via SSH)          |
| Monitoring  | Health endpoint, structured pino logs, optional Prometheus/Grafana stack   |

## Local development

```bash
# 1. Install deps
pnpm install

# 2. Boot Postgres + Redis
docker compose -f docker-compose.dev.yml up -d

# 3. Configure env
cp .env.example .env
# fill in DATABASE_URL, REDIS_URL, AUTH_SECRET, OAuth keys

# 4. Apply schema
pnpm prisma migrate dev

# 5. Run
pnpm dev
```

App will be at <http://localhost:3000>. The public renderer is at
`/u/<slug>`; the dashboard is at `/dashboard`.

## Production

See [`DEPLOYMENT.md`](./DEPLOYMENT.md) for the full Ubuntu 24.04 + Docker +
Nginx + Let's Encrypt walkthrough targeting `together.kebruni.me`.

```bash
# On the VPS, after first-time setup:
docker compose -f docker-compose.prod.yml up -d --build
```

## License

MIT
