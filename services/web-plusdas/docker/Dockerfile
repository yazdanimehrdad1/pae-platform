# syntax=docker/dockerfile:1
# web-plusdas image: the SPA built to static files, served by nginx, which also proxies /api to
# backend-ot so the browser only ever talks to its own origin.
# Build context: services/web-plusdas (never the monorepo root).
#
# One image for every environment: nothing environment-specific is baked into the bundle.
# At container start nginx renders docker/nginx/default.conf.template (API_UPSTREAM) and
# 40-app-config.sh writes /config.js (APP_API_BASE_URL). See .env.example.

# ---- build: node + npm ci from package-lock.json -------------------------------------------
FROM node:24-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---- serve: nginx ------------------------------------------------------------------------------
FROM nginx:1.30-alpine
# The official image renders /etc/nginx/templates/*.template into /etc/nginx/conf.d/ with
# envsubst at start, substituting only variables that are set (so nginx's own $uri etc. survive).
COPY docker/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY docker/config.js.template /etc/nginx/app/config.js.template
COPY --chmod=755 docker/40-app-config.sh /docker-entrypoint.d/40-app-config.sh
COPY --from=builder /app/dist /usr/share/nginx/html

# Standalone default; compose overrides it (dev stack: http://backend-ot:8000).
ENV API_UPSTREAM=http://host.docker.internal:8000 \
    APP_API_BASE_URL=/api

EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
