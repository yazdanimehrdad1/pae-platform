# web-plusdas

The PAE platform frontend: a Vite + React + TypeScript single-page app (shadcn/ui, Tailwind,
React Query). It is built to static files and served by nginx. nginx also proxies `/api/*` to
backend-ot, so the browser only ever talks to its own origin.

## Quick start

```bash
make -C services/web-plusdas install            # npm ci
make -C services/web-plusdas run                # Vite dev server on http://localhost:5174, /api -> localhost:8000
make -C services/web-plusdas lint typecheck     # eslint, tsc (both blocking)
make -C services/web-plusdas up                 # nginx container on http://localhost:5173
make -C services/web-plusdas test               # API-types drift check + vitest
make -C services/web-plusdas api-types          # regenerate API types after backend-ot's contract changes
make -C services/web-plusdas test-integration   # checks the running container (SPA + same-origin /api)
```

Normally the whole platform runs from the repo root instead: `make up` there starts web-plusdas on
http://localhost:5173 alongside backend-ot and mock-modbus.

## Runtime configuration

Nothing environment-specific is baked into the bundle. At container start:

- `APP_API_BASE_URL` (default `/api`) is written to `/config.js` as `window.__APP_CONFIG__`,
  which `index.html` loads before the app. `src/shared/config/runtime.ts` is the only reader.
- `API_UPSTREAM` (the backend-ot base URL) is rendered into the nginx config.

See `.env.example`, and `docs/same-origin.md` for why the app never calls the API cross-origin.
