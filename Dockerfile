###############################################################################
# Linkforge — multi-stage Dockerfile (Next.js standalone + worker support)
#
#   $ docker build -t linkforge .
#   $ docker run -p 3000:3000 --env-file .env.production linkforge
#
# To run the worker entrypoint instead of the web server:
#   $ docker run --env-file .env.production linkforge node /app/dist/worker/index.js
###############################################################################

# ---- 1. deps ----------------------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app

# Native deps for argon2 / sharp
RUN apk add --no-cache libc6-compat python3 make g++

COPY package.json pnpm-lock.yaml* ./
RUN corepack enable && pnpm install --frozen-lockfile

# ---- 2. builder -------------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
RUN apk add --no-cache libc6-compat python3 make g++
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN corepack enable
RUN pnpm prisma generate
RUN pnpm build

# Compile the worker too
RUN pnpm worker:build || echo "worker build skipped"

# ---- 3. runner --------------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN apk add --no-cache libc6-compat tini && \
    addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Standalone Next.js output
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Prisma + worker
COPY --from=builder --chown=nextjs:nodejs /app/prisma ./prisma
COPY --from=builder --chown=nextjs:nodejs /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder --chown=nextjs:nodejs /app/node_modules/@prisma ./node_modules/@prisma
COPY --from=builder --chown=nextjs:nodejs /app/dist ./dist

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

ENTRYPOINT ["/sbin/tini","--"]
CMD ["node", "server.js"]
