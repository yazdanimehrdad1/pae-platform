# Same-origin API calls (no CORS)

The browser only ever calls the APIs on **its own origin**: backend-ot under `/api`, and the
powerflow simulator (the Simulation page) under `/powerflow-api`. Something on that origin
forwards them server-side (`/powerflow-api/x` becomes powerflow's `/api/x`), so the browser never
makes a cross-origin request and neither backend needs CORS configuration (neither has any).

| Where | Serves the SPA | Forwards `/api/*` to backend-ot |
|---|---|---|
| Container (`make up`, root `make up`, production) | nginx on :80 (host 5173) | nginx `proxy_pass ${API_UPSTREAM}` (docker/nginx/default.conf.template) |
| Dev server (`make run`) | Vite on :5174 | Vite proxy, target `WEB_PLUSDAS_DEV_API_TARGET` (default `http://localhost:8000`) |
| Production behind the platform reverse proxy | nginx, same as the container | same, with `API_UPSTREAM` pointing at backend-ot |

`API_UPSTREAM` per environment: dev stack `http://backend-ot:8000` (deploy/compose/
web-plusdas.dev.override.yaml); standalone `make up` `http://host.docker.internal:8000`
(`WEB_PLUSDAS_API_UPSTREAM`).

| Where | Forwards `/powerflow-api/*` to powerflow's `/api/*` |
|---|---|
| Container | nginx `proxy_pass ${POWERFLOW_UPSTREAM}/api/` — dev stack `http://powerflow:8000`, standalone `http://host.docker.internal:8020` (`WEB_PLUSDAS_POWERFLOW_UPSTREAM`) |
| Dev server (`make run`) | Vite proxy with a path rewrite, target `WEB_PLUSDAS_DEV_POWERFLOW_TARGET` (default `http://localhost:8020`) |

The SPA's base for it is `getRuntimeConfig().powerflowBaseUrl` (`APP_POWERFLOW_BASE_URL`,
default `/powerflow-api`), used only through `powerflowClient` in `src/api/client.ts`.

## Rules

- **Never build an absolute API URL.** Every call goes through `src/api/client.ts`, whose base
  is `getRuntimeConfig().apiBaseUrl` (default `/api`). There are no `VITE_*` variables: the base
  comes from `/config.js` at runtime (`APP_API_BASE_URL` in the container), so one image works in
  every environment. Keep that value a same-origin path.
- **Never put a trailing slash on an API path in `src/api/*`.** Write `/sites`, not `/sites/`.
  backend-ot's routes have no trailing slash, and FastAPI's `redirect_slashes` answers a slashed
  path with a `307` to the unslashed one. Behind nginx that redirect stays on the web origin
  (nginx passes `Host` through), but it is a wasted round trip. In dev, the Vite proxy's
  `followRedirects: true` absorbs it server-side as a safety net.
- **Streaming (SSE) goes through the same proxy.** `src/api/sse.ts` reads server-sent events with
  `fetch`. nginx serves `/api/modbus-live-stream-raw-registers/` with buffering off; a new
  streaming route needs the same treatment in the nginx template.

## Why not CORS

The old setup set `VITE_RTAC_SERVER_BASE_URL=http://localhost:8000`, which baked a cross-origin
URL into the bundle, and the browser blocked it (backend-ot sends no `Access-Control-Allow-Origin`).
Adding CORS to backend-ot would make the frontend's deployment a backend concern. Same-origin
keeps the API contract as the only coupling between the two (see `contracts/README.md` at the
repo root).
