# Linkforge — Architecture

> A production-grade, scalable link-in-bio / mini-landing SaaS.
> This document captures the full system design and the MVP → Scale roadmap.

---

## 0. TL;DR

- **Frontend & API**: Next.js 15 (App Router, RSC, Route Handlers + Server
  Actions). React 19 + TypeScript. Single deployable, but logically split into
  `(marketing)`, `(auth)`, `(dashboard)`, `(admin)` and `u/[slug]` route
  groups.
- **Background workers**: BullMQ workers in a separate `apps/worker` process
  (image processing, analytics rollups, email, AI calls, webhook fan-out).
- **Persistence**: PostgreSQL 16 with Prisma; Redis 7 for cache + queues +
  rate-limit + realtime fan-out.
- **Auth**: Auth.js v5 (NextAuth) with credentials, OAuth (Google, GitHub) and
  Telegram Login Widget; TOTP 2FA; sessions stored in Postgres with refresh +
  device fingerprint; brute-force protection via Redis.
- **Storage**: S3-compatible (Cloudflare R2 in prod, MinIO in dev); image
  pipeline runs in worker (sharp + AVIF/WebP variants).
- **Payments**: Stripe (subscriptions + Checkout + customer portal +
  webhooks).
- **Edge**: Nginx reverse proxy (HTTP/2, gzip + brotli, security headers,
  rate-limit zones, websocket upgrade) terminating Let's Encrypt TLS.
- **Deploy**: Docker Compose on a single VPS for MVP (Ubuntu 24.04 + UFW +
  fail2ban). Architecture is k8s-ready — see §13.
- **Observability**: Pino structured logs → file/journald, optional Loki +
  Grafana. Prometheus exporters wired into compose for opt-in.

---

## 1. High-level system diagram

```
                        ┌─────────────────────────────────────────────┐
                        │                  Internet                    │
                        └───────────────┬─────────────────────────────┘
                                        │ 80/443 (TLS, HTTP/2)
                                        ▼
              ┌──────────────────────────────────────────────────────┐
              │                  Nginx (reverse proxy)                │
              │  • TLS termination (Let's Encrypt, auto-renew)        │
              │  • HTTP/2, gzip + brotli                              │
              │  • CSP / HSTS / X-Frame-Options / Referrer-Policy     │
              │  • limit_req zones (auth / api / public)              │
              │  • WebSocket upgrade for /api/realtime                │
              └─────────┬───────────────────────┬────────────────────┘
                        │ /                      │ /api/*  /u/*
                        ▼                        ▼
              ┌────────────────────┐    ┌────────────────────────────┐
              │  Next.js (web)     │    │  Next.js (web, same proc.) │
              │  RSC + Server      │    │  Route Handlers            │
              │  Actions           │    │  /api/auth, /api/pages …   │
              └────┬───────────┬───┘    └─────────┬──────────────────┘
                   │           │                  │
                   │           ▼                  ▼
                   │    ┌────────────┐    ┌────────────────┐
                   │    │  Postgres  │◄──►│  Prisma Client │
                   │    │ (primary)  │    └────────────────┘
                   │    └─────┬──────┘
                   │          │ logical replication / pg_basebackup
                   │          ▼
                   │    ┌────────────┐
                   │    │ Postgres   │  (read replica, optional)
                   │    │ (replica)  │
                   │    └────────────┘
                   ▼
            ┌──────────────┐
            │    Redis     │◄────────────────────┐
            │  cache +     │                     │
            │  BullMQ +    │   ┌───────────────┐ │
            │  rate-limit  │◄──┤ apps/worker   │─┘
            └──────────────┘   │  • image opts │
                               │  • email send │
                               │  • analytics  │
                               │  • AI gen     │
                               │  • webhooks   │
                               └───────────────┘

            ┌────────────────┐    ┌────────────────┐
            │  S3 / R2       │    │  Stripe API    │
            │ (asset store)  │    │ (billing)      │
            └────────────────┘    └────────────────┘
```

---

## 2. Repository layout (feature-based, monorepo-ready)

```
linkforge/
├── apps/
│   ├── web/                    # Next.js 15 app (UI + API + Server Actions)
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── (marketing)/        # public landing, pricing, blog
│   │   │   │   ├── (auth)/             # login, register, verify, 2fa
│   │   │   │   ├── (dashboard)/        # /dashboard/...  authed
│   │   │   │   ├── (admin)/            # /admin/...      role=ADMIN
│   │   │   │   ├── u/[slug]/           # public renderer
│   │   │   │   └── api/                # route handlers
│   │   │   │       ├── auth/[...nextauth]/route.ts
│   │   │   │       ├── pages/          # CRUD pages
│   │   │   │       ├── blocks/         # CRUD blocks (drag-and-drop)
│   │   │   │       ├── analytics/      # ingest + query
│   │   │   │       ├── billing/        # stripe webhooks + checkout
│   │   │   │       ├── ai/             # AI helpers
│   │   │   │       ├── webhooks/       # outbound webhooks management
│   │   │   │       ├── short/[code]/   # short-link redirect
│   │   │   │       ├── qr/             # QR generator
│   │   │   │       └── health/route.ts
│   │   │   ├── components/
│   │   │   │   ├── ui/                 # shadcn primitives
│   │   │   │   ├── builder/            # editor canvas, block list, inspector
│   │   │   │   ├── dashboard/          # nav, stats cards, charts
│   │   │   │   ├── public/             # block renderers (link, video, etc.)
│   │   │   │   ├── marketing/          # hero, pricing, testimonials, faq
│   │   │   │   └── shared/             # avatar, theme-toggle, copy-button…
│   │   │   ├── features/               # feature-grouped logic
│   │   │   │   ├── auth/
│   │   │   │   ├── builder/
│   │   │   │   ├── analytics/
│   │   │   │   ├── billing/
│   │   │   │   ├── ai/
│   │   │   │   └── admin/
│   │   │   ├── lib/                    # cross-cutting infra (no JSX)
│   │   │   │   ├── auth.ts             # auth.js config
│   │   │   │   ├── prisma.ts           # singleton Prisma client
│   │   │   │   ├── redis.ts            # ioredis singleton
│   │   │   │   ├── queue.ts            # BullMQ queues + add helpers
│   │   │   │   ├── rate-limit.ts       # token-bucket on Redis
│   │   │   │   ├── env.ts              # zod-typed env schema
│   │   │   │   ├── analytics.ts        # event normalisation helpers
│   │   │   │   ├── seo.ts              # metadata + JSON-LD helpers
│   │   │   │   ├── geo.ts              # IP → country (header / MaxMind)
│   │   │   │   ├── crypto.ts           # encrypt/decrypt secrets at rest
│   │   │   │   ├── storage.ts          # S3 presigned uploads
│   │   │   │   ├── stripe.ts
│   │   │   │   ├── ai.ts
│   │   │   │   └── utils.ts
│   │   │   ├── server/
│   │   │   │   ├── actions/            # 'use server' actions (RHF + zod)
│   │   │   │   └── services/           # pure domain logic, unit-testable
│   │   │   ├── store/                  # zustand client stores (UI-only)
│   │   │   ├── styles/
│   │   │   └── types/
│   │   ├── public/
│   │   ├── tests/
│   │   ├── next.config.ts
│   │   └── tailwind.config.ts
│   └── worker/                  # BullMQ workers (separate process)
│       └── src/
│           ├── index.ts
│           ├── queues.ts
│           └── jobs/
│               ├── image-process.ts
│               ├── analytics-rollup.ts
│               ├── email-send.ts
│               ├── ai-generate.ts
│               └── webhook-deliver.ts
├── packages/
│   ├── db/                      # Prisma schema + generated client
│   │   ├── prisma/
│   │   │   ├── schema.prisma
│   │   │   ├── seed.ts
│   │   │   └── migrations/
│   │   └── package.json
│   ├── ui/                      # shared design primitives (optional split)
│   ├── eslint-config/
│   └── tsconfig/
├── nginx/
│   ├── conf.d/
│   │   └── linkforge.conf
│   └── snippets/
│       ├── ssl.conf
│       └── security-headers.conf
├── scripts/
│   ├── setup-vps.sh             # bootstrap Ubuntu 24.04
│   ├── ssl-init.sh              # first-time certbot
│   ├── deploy.sh                # idempotent rolling deploy
│   ├── backup-postgres.sh       # cron'd nightly + retain N days
│   └── restore-postgres.sh
├── .github/workflows/
│   ├── ci.yml                   # lint + typecheck + test + build
│   └── deploy.yml               # SSH deploy with zero-downtime
├── docker-compose.yml           # dev (postgres + redis + minio)
├── docker-compose.prod.yml      # prod (web + worker + db + redis + nginx + certbot)
├── Dockerfile                   # multi-stage for `web` and `worker`
├── package.json                 # root workspaces
├── pnpm-workspace.yaml
├── turbo.json                   # optional pipelines
├── tsconfig.base.json
├── ARCHITECTURE.md
├── DEPLOYMENT.md
└── README.md
```

> **MVP shortcut.** The current scaffold collapses `apps/web` into the repo
> root for simplicity (single Next.js project + a thin `worker/` directory).
> The folder layout above is the target once we extract a workspace. The
> internal modules (`features/`, `lib/`, `server/`, `components/`) already
> follow the final naming so the eventual split is mechanical.

---

## 3. Domain model (Prisma)

The full source is in [`prisma/schema.prisma`](./prisma/schema.prisma). Core
entities and their relationships:

```
User ──┬──< Account            (OAuth identity per provider)
       ├──< AuthSession        (refresh/device sessions)
       ├──< TwoFactor          (TOTP secret, recovery codes)
       ├──< Page (1:N)
       │      ├──< Block (1:N, ordered, JSON content)
       │      ├──< Theme (1:1)
       │      └──< CustomDomain (1:1, optional)
       ├──< ShortLink          (per-user URL shortener)
       ├──< AnalyticsEvent     (clicks/views, partitioned)
       ├──< AuditLog           (admin / security trail)
       ├──< ApiKey             (hashed, RBAC scoped)
       ├──< Webhook
       ├──< Subscription       (stripe billing)
       └──< Referral           (affiliate / referral code)

PageTemplate              (admin-curated templates)
FeatureFlag               (key:value, per-environment)
SupportTicket
ContentReport             (user-submitted moderation reports)
```

### 3.1 Indexing & data lifecycle

- `Page.slug` is **unique**; `Page.userId, slug` doubly indexed for dashboard
  list queries.
- `Block.pageId` + `Block.order` indexed; reorder is a single transaction.
- `AnalyticsEvent` is **append-only**; partition by month
  (`pg_partman` recommended) and TTL raw events to 90 days, with rolled-up
  aggregates retained indefinitely (`AnalyticsDaily`).
- All entities carry `createdAt`, `updatedAt`. `User`, `Page`, `Block` carry
  `deletedAt` for soft-delete.
- `User.role` is an enum (`USER | PRO | ADMIN | SUPPORT`) used for RBAC.

### 3.2 Why JSON for `Block.content`?

Blocks are highly polymorphic (link, embed, FAQ, gallery, form, …). Instead of
a table per block kind we store a versioned JSON blob and validate it server-
side with a Zod schema keyed by `Block.type`. This keeps migrations cheap and
the editor extensible. For analytics-heavy fields (URL, target, label) we
hoist a few indexed columns onto `Block` itself.

---

## 4. API surface (REST + Server Actions)

All write paths support BOTH a typed Server Action (preferred from React) and
a JSON Route Handler (used by mobile, integrations and the public iframe
embeds). Inputs are validated with Zod; responses are typed via a shared
`ApiResponse<T>` envelope.

### 4.1 Auth (`/api/auth/*`)

Provided by Auth.js v5. We additionally expose:

| Method | Path                          | Purpose                                    |
| ------ | ----------------------------- | ------------------------------------------ |
| POST   | `/api/auth/register`          | Email + password sign-up (rate-limited)    |
| POST   | `/api/auth/verify-email`      | Confirm magic-link token                   |
| POST   | `/api/auth/forgot-password`   | Send reset email (rate-limited)            |
| POST   | `/api/auth/reset-password`    | Apply new password with reset token        |
| POST   | `/api/auth/2fa/enroll`        | Generate TOTP secret + QR                  |
| POST   | `/api/auth/2fa/verify`        | Verify TOTP code, mark session as 2FA-ok   |
| GET    | `/api/auth/sessions`          | List active device sessions                |
| DELETE | `/api/auth/sessions/:id`      | Revoke a session                           |

### 4.2 Pages (`/api/pages/*`)

| Method | Path                          | Purpose                              |
| ------ | ----------------------------- | ------------------------------------ |
| GET    | `/api/pages`                  | List my pages (paginated)            |
| POST   | `/api/pages`                  | Create page (slug check)             |
| GET    | `/api/pages/:id`              | Read with blocks + theme             |
| PATCH  | `/api/pages/:id`              | Patch metadata / theme               |
| DELETE | `/api/pages/:id`              | Soft-delete                          |
| POST   | `/api/pages/:id/duplicate`    | Clone with new slug                  |
| POST   | `/api/pages/:id/publish`      | Toggle published flag                |

### 4.3 Blocks

| Method | Path                                  | Purpose                  |
| ------ | ------------------------------------- | ------------------------ |
| POST   | `/api/pages/:id/blocks`               | Create block             |
| PATCH  | `/api/pages/:id/blocks/:blockId`      | Update content           |
| DELETE | `/api/pages/:id/blocks/:blockId`      | Remove                   |
| POST   | `/api/pages/:id/blocks/reorder`       | Bulk reorder (atomic)    |

### 4.4 Public renderer + tracking

| Method | Path                       | Purpose                                    |
| ------ | -------------------------- | ------------------------------------------ |
| GET    | `/u/:slug`                 | SSR mini-landing                           |
| POST   | `/api/analytics/track`     | Ingest view/click events (non-blocking)    |
| GET    | `/short/:code`             | 302 redirect + click event                 |

### 4.5 Analytics, billing, AI, admin

- `/api/analytics/*` — server-side aggregated queries (charts, top links).
- `/api/billing/checkout` — start Stripe Checkout session.
- `/api/billing/webhook` — Stripe webhook (raw body verification).
- `/api/ai/bio`, `/api/ai/theme`, `/api/ai/cta`, `/api/ai/seo` — AI helpers.
- `/api/admin/*` — gated by `requireRole('ADMIN')`.

### 4.6 Conventions

- **Versioning**: prefix `/api/v1` once we ship public API keys (out of MVP).
- **Pagination**: `?cursor=` (opaque base64) + `?limit=` (max 100).
- **Filtering**: `?filter[field]=value`, validated per-endpoint.
- **Idempotency**: writes accept `Idempotency-Key` header (stored 24h in
  Redis).
- **Errors**: RFC 7807 problem+json with `code`, `message`, `details`.
- **Documentation**: zod-to-OpenAPI generator → `/api/openapi.json` (Swagger
  UI mounted at `/api/docs` in non-prod or for ADMIN).

---

## 5. Auth & session architecture

```
 register / login form ─► /api/auth/* (Auth.js)
                          │  • argon2id password hash
                          │  • brute-force counter (Redis: auth:fails:<ip>)
                          │  • IP geo + device fingerprint (UA + Sec-CH-UA)
                          ▼
                    AuthSession row
                    │  id (cuid)
                    │  userId
                    │  expiresAt        (sliding, 30d max)
                    │  refreshTokenHash (rotated on every use)
                    │  deviceLabel, ip, ua, country
                    │  twoFactorPassedAt
                    │
                    ▼
        HttpOnly Secure SameSite=Lax cookie
        ── linkforge.session=<jwt>  (short-lived 15m JWT,
                                     refresh handled server-side)
```

- **Suspicious-login detection.** A login from a new country / new device
  triggers an email + must clear an additional check (TOTP if enrolled,
  otherwise email magic-link). The current session is marked
  `requiresStepUp=true` for sensitive actions (billing change, password
  change, API-key creation, custom-domain attach) until cleared.
- **Brute-force.** `auth:fails:<ip>` and `auth:fails:<email>` counters with
  exponential lockout (15s → 1m → 5m → 1h). After 10 failures we challenge
  the IP with a captcha.
- **2FA.** TOTP via `otplib`; recovery codes (10 single-use, hashed). Backup
  codes downloadable once on enrolment. WebAuthn is on the roadmap.
- **OAuth.** Google + GitHub via Auth.js; Telegram via the Telegram Login
  Widget (verifies HMAC against the bot token).
- **Account linking.** Same email → existing user; otherwise we ask the
  user to confirm linking before merging.
- **Device sessions.** `/dashboard/settings/security` lists every
  `AuthSession` and lets the user revoke one, all-other, or all (forces
  full re-login).

---

## 6. Page builder

### 6.1 Editor architecture

```
┌───────────────────────────────────────────────────────────────┐
│  /dashboard/pages/[id]/edit                                   │
│  ┌─────────┐  ┌────────────────────────────┐  ┌─────────────┐ │
│  │ Block   │  │      Canvas (live preview) │  │ Inspector   │ │
│  │ palette │  │  ┌───────────────────────┐ │  │ (selected   │ │
│  │ • Link  │  │  │  responsive frame     │ │  │ block       │ │
│  │ • Text  │  │  │  ┌─────────────────┐  │ │  │ properties) │ │
│  │ • Video │  │  │  │  block          │◄─┼─┼──┤             │ │
│  │ • Embed │  │  │  └─────────────────┘  │ │  │ • style     │ │
│  │ • FAQ   │  │  │  ┌─────────────────┐  │ │  │ • content   │ │
│  │ • Form  │  │  │  │  block          │  │ │  │ • a11y      │ │
│  │ • …     │  │  │  └─────────────────┘  │ │  │ • SEO       │ │
│  └─────────┘  │  └───────────────────────┘ │  └─────────────┘ │
│               │  device: phone / tablet /   │                  │
│               │   desktop  (Tailwind br.)   │                  │
│               └────────────────────────────┘                  │
└───────────────────────────────────────────────────────────────┘
```

- **Drag & drop** uses `@dnd-kit/core` (accessibility, keyboard support).
  Reordering issues a single `PATCH /blocks/reorder` with the new array of
  ids; the server validates ownership and writes inside a transaction with
  `update` per row using a single CTE.
- **Live preview** is the same React block renderer used by the public
  page; the editor passes `isEditing` to disable links/forms in preview.
- **State**. Zustand store keeps the unsaved working copy. A debounced
  autosave (1 s) calls a Server Action; conflicts are resolved last-writer-
  wins per block but each block carries `version` so concurrent tab edits
  surface a "page changed elsewhere" toast.
- **Block schema versioning**. Every block JSON has `_v: 1`; migration
  functions run on read so old data keeps working.

### 6.2 MVP blocks

| Type        | Notes                                               |
| ----------- | --------------------------------------------------- |
| `link`      | label, url, icon, style, click-tracking             |
| `text`      | rich text (markdown subset, sanitized)              |
| `button`    | label, url, variant (primary/ghost/outline), CTA    |
| `image`     | uploaded asset, alt, link, lazy                     |
| `video`     | url, autoplay/muted/loop, captions                  |
| `embed`     | YouTube / TikTok / Spotify / Telegram / SoundCloud  |
| `divider`   | spacer / hairline                                   |
| `social`    | row of icons → social URLs                          |
| `form`      | name + email + message → leads + email notify       |
| `faq`       | array of {q,a}                                      |
| `countdown` | targetAt, finishedText                              |
| `gallery`   | grid of images                                      |
| `donation`  | preset amounts → Stripe Checkout (PRO)              |
| `product`   | digital good (PRO, requires billing on)             |
| `map`       | OSM/Mapbox embed                                    |

Adding a block = (a) Zod schema in `features/builder/blocks/<type>.ts`,
(b) renderer in `components/public/blocks/<Type>Block.tsx`, (c) inspector
in `components/builder/inspectors/<Type>Inspector.tsx`. Everything else
(palette, drag, save) is generic.

### 6.3 Themes

A `Theme` is a JSON object of design tokens (colors, font, radii, gradients,
background). Built-in themes ship as seed data; PRO users can override every
token. The public renderer maps tokens onto CSS variables, so theming is
zero-runtime — Tailwind `bg-[var(--lf-accent)]` etc.

---

## 7. Public renderer

```
GET /u/:slug
  ├─ Cache key: page:slug:<slug>:v<page.version>  (Redis, 5 min)
  ├─ ISR / on-demand revalidate when page.version bumps
  ├─ Returns SSR HTML with:
  │    • <head> SEO + OpenGraph + Twitter + JSON-LD (Person/Organization)
  │    • <body> theme variables, blocks
  │    • <script defer src="/_lf/track.js"> (≤2 KB)
  └─ Edge headers:
       Cache-Control: public, max-age=0, s-maxage=300, stale-while-revalidate=86400
       X-Robots-Tag: index,follow (unless page.private)
```

- **Tracking.** A 1.6 KB inline script fires `pageview` once and `click` on
  every `[data-track-block-id]` anchor. Uses `navigator.sendBeacon` to a
  Route Handler that appends to a Redis stream; the worker drains the stream
  and writes batched rows into `AnalyticsEvent`. This keeps the public
  request path < 5 ms.
- **Bot filtering.** UA + `Sec-Fetch-Site` + ASN reputation list + a small
  Redis "rolling unique IPs" set for de-duplication.
- **OG image.** Generated lazily via `@vercel/og` from page theme on first
  request, cached on disk.

---

## 8. Analytics

```
public page  ─►  POST /api/analytics/track  (≤5 ms)
                       │
                       ▼
            Redis Stream:  analytics:events
                       │
                       ▼
       ┌──── apps/worker (analytics-rollup job) ──────────┐
       │  XREAD batches → enrich (geo, ua-parse) →         │
       │  COPY into AnalyticsEvent (partitioned by month)  │
       │  upsert into AnalyticsDaily aggregates            │
       │  publish realtime delta on Redis pub/sub          │
       └───────────────────────────────────────────────────┘
                       │
                       ▼
   /dashboard/analytics  ─► RSC reads AnalyticsDaily for charts;
                           realtime banner subscribes via WS to deltas.
```

Aggregates we maintain:

- `AnalyticsDaily(pageId, day, views, uniques, clicks)` — primary chart data.
- `AnalyticsTopBlock(pageId, day, blockId, clicks)` — top-CTA chart.
- `AnalyticsCountry(pageId, day, country, views)` — GEO map.
- `AnalyticsDevice(pageId, day, device, browser, os, count)` — pie charts.

UTM parameters are normalised on ingest (`utm_source`, `utm_medium`,
`utm_campaign`, `utm_term`, `utm_content`) and surfaced in the dashboard
funnel view.

---

## 9. AI features

Implemented behind a single `lib/ai.ts` adapter so providers can be swapped:

- `generateBio({tone, length, keywords})` — returns 3 variants.
- `generateTheme({mood, brand})` — returns design tokens (colors,
  gradients, font pairing) validated by Zod before being applied.
- `optimizeCTA({block, context})` — rewrites CTA copy with A/B variants.
- `seoAudit({page})` — returns metadata suggestions + JSON-LD diff.
- `usernameSuggest({hint})` — returns 5 unused slugs.

All AI calls go through BullMQ (`ai-generate` queue) with per-user rate
limits (Redis token bucket: 30/h free, 600/h PRO) and audit logging.

---

## 10. Monetisation

- **Free**: 1 page, all core blocks, no custom domain, Linkforge branding.
- **PRO** (subscription, monthly/yearly): unlimited pages, custom domain,
  analytics > 90 days, AI features, products / donations, scheduled
  publishing, A/B tests, themes marketplace.
- **Pay-per-product** (no subscription): user receives 95% of digital
  product sales; Stripe Connect Express or platform-fee model — out of MVP.
- **Affiliate / referral**: each user has a referral code; referred PRO
  signups give 30% MRR for 12 months. Tracked via `Referral` table.
- **Stripe**: Checkout session for first subscription, customer portal for
  managing it, webhook synchronises `Subscription` and `User.role`.

---

## 11. Security architecture

| Threat                        | Mitigation                                              |
| ----------------------------- | ------------------------------------------------------- |
| SQL injection                 | Prisma parameterised queries; never raw concat          |
| XSS in user content           | DOMPurify on markdown render; `dangerouslySetInnerHTML` |
|                               | only for vetted embed snippets; CSP `script-src 'self'` |
| CSRF                          | Same-origin + Auth.js CSRF token on form posts          |
| Brute-force / credential stuf.| Redis counters + lockouts + captcha challenge           |
| Account takeover              | New-device email + 2FA step-up + session list           |
| Open redirects                | Whitelist hosts on social / OAuth callback              |
| SSRF (image fetching)         | Worker only fetches via DNS resolver that blocks RFC1918|
| Rate-limit bypass             | Limit per IP **and** per user                           |
| File upload abuse             | Presigned PUT directly to S3 with size + mime           |
|                               | restrictions; sharp re-encodes to AVIF/WebP             |
| Secrets at rest               | App-level AES-GCM with a key from env (rotatable)       |
| Audit                         | `AuditLog` for every privileged action (RBAC, admin,    |
|                               | billing, custom domain, password change)                |
| Headers                       | HSTS, CSP, X-CTO, X-Frame-Options, Referrer-Policy,     |
|                               | Permissions-Policy — see `nginx/snippets/security-      |
|                               | headers.conf`                                           |
| TLS                           | Let's Encrypt; modern profile (TLS 1.2 + 1.3 only)      |
| Container hardening           | Non-root user, read-only rootfs where possible,         |
|                               | dropped capabilities, no docker.sock                    |
| Spam in forms / signup        | hCaptcha or Cloudflare Turnstile, honey-pot, Redis IP   |
|                               | rate-limit                                              |

A `SECURITY.md` will document responsible-disclosure once we open the repo.

---

## 12. Performance budget

- **TTFB** for `/u/:slug`: < 50 ms (Redis hit) / < 200 ms (cold).
- **LCP** mobile: < 2.0 s on Slow-4G; **CLS** < 0.05.
- **Lighthouse**: 95+ on Performance / Accessibility / SEO / Best
  Practices for the public renderer.
- **JS payload** for public page: < 30 KB gzipped (renderer is mostly
  RSC; the only client JS is the tracking pixel + a few interactive
  blocks like form / countdown / gallery, lazy-loaded).
- **Image pipeline**: AVIF + WebP variants generated by worker; served
  via `<picture>` with `loading="lazy"` and explicit `width/height`.
- **Caching** layers:
  - Nginx static + immutable for `_next/static/*`.
  - Redis page cache for `/u/:slug` HTML by `(slug, version)`.
  - Browser cache + `stale-while-revalidate`.

---

## 13. Scaling strategy

- **MVP**: single VPS — `nginx + web + worker + postgres + redis` in one
  Docker Compose. Vertical scale (CPU/RAM bumps).
- **Growth**: extract Postgres + Redis to managed services (Neon,
  RDS / Upstash, Redis Cloud). Run two `web` replicas behind a load
  balancer; one `worker` replica per queue with concurrency tuned per
  queue.
- **Scale**:
  1. Move to Kubernetes (the Dockerfile already produces a multi-arch
     non-root image; the same image runs in compose and k8s).
  2. Postgres read-replicas; Prisma's `replicas` extension routes reads.
  3. Redis cluster (or Upstash) for queues; partition queues per shard.
  4. CDN (Cloudflare / Bunny) in front of Nginx; Nginx becomes the
     origin and only handles Server Actions / API.
  5. Edge functions for `/u/:slug` (Vercel Edge / Cloudflare Workers)
     hitting a regional Postgres replica.
  6. Per-tenant data isolation for enterprise (schema-per-tenant on
     Postgres).
- **Background processing**: BullMQ `redis://` is portable;
  workers are stateless and scale by concurrency × replicas.
- **Custom domains**: a dedicated nginx config with `proxy_set_header
  Host $host;` plus a Host-based router in Next.js; SSL via certbot's
  DNS-01 or `lego` automation.
- **WebSockets / realtime**: in MVP we use a single Next.js handler; at
  scale we run a dedicated `apps/realtime` service (Socket.IO) behind
  Nginx upgrade.

---

## 14. Observability

- **Logging**. Pino JSON to stdout; Docker captures it; `vector` /
  `promtail` ships to Loki (optional). Each request gets a `req-id`
  correlated across web + worker.
- **Metrics**. `/api/health` returns liveness; `/api/metrics` (gated)
  exposes Prometheus counters (HTTP latency, queue depth, DB pool).
- **Errors**. Sentry SDK on both web and worker if `SENTRY_DSN` set.
- **Uptime**. External ping (UptimeRobot / Better Stack) hits
  `https://together.kebruni.me/api/health` every minute.
- **Alerting**. Grafana alerts on: 5xx rate > 1 %/5 min, DB connection
  pool > 80 %, queue depth > 1 000, certbot expiry < 7 days.

---

## 15. Testing strategy

- **Unit**: Vitest for `lib/` and `server/services/` (pure functions);
  fast, in-memory, no DB.
- **Integration**: Vitest + a throw-away Postgres container (`testcontainers`)
  for Prisma-touching code (services, route handlers).
- **Component / RSC**: Playwright Component Tests for the builder
  (drag-and-drop) and renderer (block snapshot tests).
- **End-to-end**: Playwright drives the full app (sign-up → create page →
  add blocks → publish → public visit → analytics).
- **Contract**: zod-derived OpenAPI spec is checked against route
  handlers in CI (no drift).
- **Linting**: ESLint (next/core-web-vitals, @typescript-eslint, unused-
  imports); Prettier; `tsc --noEmit`; `prisma format` + `prisma validate`.

CI runs lint → typecheck → unit → integration → build; nightly job runs
the full e2e suite.

---

## 16. Roadmap

### MVP (this PR)

- [x] Repository scaffold + workspaces-ready layout
- [x] Prisma schema (full v1)
- [x] Auth.js (credentials + OAuth + email magic-link), TOTP 2FA
- [x] Dashboard shell (pages list, settings, analytics placeholder)
- [x] Page builder (blocks: link, text, button, image, embed, divider, social)
- [x] Public renderer with SEO + JSON-LD + click tracking
- [x] Redis-backed rate-limit + analytics ingest
- [x] BullMQ worker scaffold + image / analytics-rollup jobs
- [x] Docker Compose (dev + prod), Nginx config, Let's Encrypt
- [x] GitHub Actions CI/CD with SSH zero-downtime deploy
- [x] DEPLOYMENT.md + .env.example

### v1.1 — Creator monetisation

- Stripe subscriptions (PRO) + customer portal + webhook reconciler
- `donation` + `product` blocks (Stripe Checkout)
- Custom domains (DNS verification + per-domain Nginx + lego SSL automation)
- A/B testing (variant blocks; bandit allocator using analytics events)

### v1.2 — Growth & AI

- AI bio / theme / CTA / SEO audit / username suggestor
- Audience segmentation + smart funnels (UTM + behaviour cohorts)
- Lead scoring on form submissions
- Themes marketplace (creator royalties via Stripe Connect)
- Telegram bot (publish updates from Telegram, analytics digests)

### v1.3 — Scale

- Kubernetes manifests / Helm chart
- Postgres read replicas + Redis cluster
- CDN in front of Nginx
- Workspace isolation (schema-per-tenant) for enterprise

### v2.0 — Platform

- Public REST API + OAuth apps + Webhooks (already wired in DB)
- Mobile app (Expo) sharing the OpenAPI client
- Marketplace of community-built blocks (sandboxed iframe runtime)

---

## 17. Unique-to-Linkforge ideas (vs. plain Taplink/Linktree)

- **AI auto-landing optimiser** — nightly job that re-ranks blocks based on
  CTR per visitor segment (country, device, time-of-day) and suggests an
  optimised order; user can accept with one click.
- **Smart bio personalisation** — public renderer can serve a different
  hero copy / CTA for visitors arriving from a given UTM / referrer /
  country, all configured visually.
- **Dynamic themes** — themes can react to time-of-day, weather (via a
  geo-locked weather API), or a calendar (e.g. dark mode at night, festive
  palette during campaigns).
- **AI analytics insights** — weekly digest written by an LLM
  ("clicks dropped 18 % this week, mostly Instagram traffic from Brazil —
   here's a draft fix"), shippable as email or Telegram message.
- **Auto CTA optimisation** — bandit-optimised CTA copy across variants,
  no analytics knowledge required.
- **Audience segments + smart funnels** — visual rule builder ("first-time
  visitor, mobile, came from Instagram → show donation CTA").
- **Lead scoring** — form submissions are scored (recency, country, device,
  referrer) and surfaced in dashboard with a CRM-style inbox.
- **Creator economy** — themes marketplace, paid subscriptions to a
  creator's "private link page", gated content blocks.
- **Viral mechanics** — every public page has an opt-in "Made with
  Linkforge" badge that funnels referrals; a shareable QR code / OG image
  generator with auto-branded variants.

---

## 18. Glossary

- **Page**. A user-owned mini-landing exposed at `/u/:slug` (or a custom
  domain). Has a theme, an ordered list of blocks, SEO metadata, optional
  password.
- **Block**. A typed, JSON-content unit inside a page (link, text, embed…).
- **Slug**. The URL-safe public identifier of a page. Reserved words are
  stored in `ReservedSlug` and rejected at sign-up.
- **AuthSession**. A long-lived server-side session row, complementary to
  Auth.js JWT cookies; allows revocation and device listing.
- **AnalyticsEvent**. A single user interaction (view / click) on a public
  page; rolled up into `AnalyticsDaily` for fast charting.
