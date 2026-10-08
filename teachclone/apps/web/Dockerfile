FROM node:20-alpine AS builder

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY . .

# Build for production
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# ── Production stage ──────────────────────────────────────────────────────
FROM node:20-alpine AS runner

RUN corepack enable

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000 || exit 1

CMD ["node", "node_modules/.bin/next", "start"]
