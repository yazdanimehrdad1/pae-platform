# web-plusdas

Owns: the PAE platform UI, a Vite + React 18 + TypeScript single-page app (shadcn/ui, Tailwind 3,
React Query, react-router v6). It is built to static files, served by nginx, and nginx also
proxies `/api/*` to backend-ot on the same origin.
Does NOT own: any API or data (backend-ot owns sites/devices/points/readings/streaming), the
API contract (backend-ot publishes it), or the production reverse proxy in front of it.

## The invariant: this service stays extractable. Read this first
It must stay possible to move this directory into its own repo with
`git subtree split --prefix=services/web-plusdas` in an afternoon. So:
- **It depends only on `contracts/` and its own files.** Never import from, reference, or read
  `services/<other>/` (`../backend-ot/...`, a tsconfig/vite alias into another service, a
  Dockerfile `COPY` from outside). Talk to backend-ot over HTTP, at `/api` only.
- **Nothing outside this directory imports from it.** Scripts and other services never read
  its files (the dev stack's `deploy/compose/` include is the one exception).
- **Everything it needs lives here:** package.json, package-lock.json, tsconfig, eslint config,
  Dockerfile, Makefile, compose.yaml, .env.example. No root package.json and no workspace
  (npm/pnpm/yarn/Turbo/Nx): the root coordinates only through its Makefile and deploy/compose/.
- **Docker build context is this directory.** `contracts/` is NOT in it, so the generated API
  types are committed here (`src/api/generated/`), never read from `../../contracts` at build
  time. `scripts/api-types.mjs` is the one place that knows the contract's path; on extraction,
  only it (or the `@contracts/backend-ot` alias) changes.
- `make check-boundaries` (root) enforces the path rules for *.ts/*.tsx/*.js/package.json/
  tsconfig*.json: a `../` path may leave this service only into `contracts/`.

## Commands
Run from the repo root as `make -C services/web-plusdas <target>` (or `make <target>` here). Same
Makefile on Windows: it runs recipes in Git for Windows' sh. `make help` lists all. **npm only**:
dependencies are pinned in `package-lock.json`; host targets run `npm ci` first when
`node_modules` is missing or stale. Node **24** (`.nvmrc`, `engines`). Ask before adding a dependency.
- Setup: `make install` (`npm ci`).
- Lint: `make lint` (`eslint .`, 0 errors required, pre-commit enforced) · `make lint-fix` /
  `make format` (`eslint --fix`; there is no Prettier).
- Types: `make typecheck` (`tsc -p tsconfig.app.json --noEmit`, blocking; root `make check` runs it).
- Tests: `make test` runs the API-types drift check, then vitest (`src/**/*.test.ts(x)`, next to the
  code; Node by default, `// @vitest-environment jsdom` for a test that needs a DOM; setup in
  `src/test/setup.ts`). No Docker. `make test-integration` runs `scripts/check_same_origin.mjs`
  against the **running** container (SPA fallback, cache headers, `/config.js`, `/api/healthz` +
  `/api/sites` through the web origin). It needs the dev stack up.
- API types: `make api-types` regenerates `src/api/generated/backend-ot.ts` after backend-ot's
  contract changes (`make test` fails until you do). Then fix whatever `make typecheck` reports.
- Dev server: `make run` (Vite on http://localhost:**5174**, `/api` proxied to
  `WEB_PLUSDAS_DEV_API_TARGET`, default `http://localhost:8000` = the dev stack's backend-ot).
- Development normally uses the whole platform from the **repo root** (`make up`, UI on
  http://localhost:5173). Running this service alone is the exception: `make down` at the root
  first. `build`/`rebuild`/`up` refuse while the dev stack runs.
- Standalone container: `make up` / `down` / `logs` / `ps` / `restart` / `clean` (`compose.yaml`,
  project `web-plusdas`, host port `WEB_PLUSDAS_HTTP_PORT`=5173, nginx upstream
  `WEB_PLUSDAS_API_UPSTREAM`, default `http://host.docker.internal:8000`). `down-all` is destructive:
  only when the user asks.
- Checks: the root `test-runner` agent runs lint/tests and reports only failures.

## Layout
- `src/api/`: the only place that calls the backend. `client.ts` (`request`, `client.get/post/put/
  delete/action`, `getErrorMessage` for FastAPI `detail`), one module per resource (`sites.ts`,
  `devices.ts`, `historian.ts`, `modbusStream.ts`), `sse.ts` (fetch-based server-sent events),
  `generated/backend-ot.ts` (generated, don't edit). Pages use them through React Query. To add
  or change a call, use the `add-api-call` skill.
- `src/features/<feature>/`: pages + their hooks/lib. `src/shared/`: layout, contexts (auth,
  notes), types, config. `src/components/ui/`: shadcn components (generated; keep edits minimal).
- `docker/`: `Dockerfile` (node:24 build → nginx:1.30 serve), `nginx/default.conf.template`,
  `config.js.template` + `40-app-config.sh` (writes `/config.js` at container start).
- `Tests/`, `src/shared/test/`, `src/features/sld/test/`: static mock data, not tests.
- `docs/`: `same-origin.md` (why no CORS), `backend-gaps.md` (what the mocked pages need from
  backend-ot).

## Runtime config and same-origin (details: `docs/same-origin.md`)
- **No build-time configuration.** No `VITE_*` variables and no `import.meta.env` reads. Runtime
  values come from `window.__APP_CONFIG__`, set by `/config.js` before the bundle loads, and are
  read only through `getRuntimeConfig()` (`src/shared/config/runtime.ts`). To add a value, add it
  there, to `docker/config.js.template` + `40-app-config.sh` (the envsubst list), to
  `public/config.js` (dev default), and to `.env.example`.
- **API calls are same-origin `/api/...` only.** Never an absolute URL, never CORS. Never put a
  trailing slash on an API path (backend-ot 307s it).
- A new **streaming** route needs its own nginx location with `proxy_buffering off` (like
  `/api/modbus-live-stream-raw-registers/`).

## Contracts (rules: `contracts/README.md`, procedure: root `contracts` skill)
- **Consumes** `contracts/openapi/backend-ot.openapi.json` through generated types (openapi-typescript),
  imported only as `@contracts/backend-ot`. Wire types in `src/shared/types/` are aliases of
  generated schemas (`components['schemas'][...]`), never hand-written. The exceptions are UI view
  models (`Site`, `Device`, ...) and the SSE event payloads, which the contract doesn't describe.
- Option lists for contract enums are `Record<Enum, Label>` (e.g. `DEVICE_TYPE_LABELS`), so an
  enum change in backend-ot fails `make typecheck` here.
- A route that isn't in the contract can't be called: backend-ot adds it first. What the mocked
  pages need is in `docs/backend-gaps.md`.
- Provides no contract (no `contract` target).

## Gotchas
- `strict: false` and `noImplicitAny: false` in tsconfig (inherited): the compiler won't catch
  nulls, and `z.infer` marks every zod field optional (hence the cast in `ModbusStreamForm.toRequest`).
- Mocked, not wired to backend-ot (the backend has no API for them yet): auth
  (`src/shared/contexts/auth.tsx` accepts anything), HealthPage, SLD, and Notes (localStorage).
  See `docs/backend-gaps.md`.
- `.env.development` / `.env.production` may exist locally (untracked, gitignored) from the old
  repo. No code reads them; never read or edit them.
- On Windows, a Node script that calls `process.exit()` after `fetch` can crash (libuv assertion).
  Set `process.exitCode` instead (see `scripts/check_same_origin.mjs`).
