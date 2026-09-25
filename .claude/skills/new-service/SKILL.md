---
name: new-service
description: Create a new service in this monorepo scaffolded to the service convention and registered everywhere it must be — a Python/FastAPI API service (optimizer, powerflow, ...) or a Node frontend (Vite + React SPA like web-plusdas). Use for "add a new service", "scaffold the optimizer", "create a powerflow service", "start a new microservice", "add another frontend/UI/console".
---

# Scaffold a new service

`scaffold.py` writes `services/<name>/` from `templates/<kind>/`:
- **`--kind python`** (default): a FastAPI app in `src/<package>/` with `/api/healthz`, config via
  pydantic-settings, a pytest suite, a uv-based Dockerfile, and an OpenAPI contract in
  `contracts/openapi/<name>.openapi.json`.
- **`--kind node`**: a Vite + React + TypeScript (strict) SPA served by nginx, with `/api`
  proxied same-origin to backend-ot. It has runtime config via `/config.js`, API types generated
  from backend-ot's contract (`@contracts/backend-ot`), vitest, and a same-origin integration
  check. It has the same layout as `services/web-plusdas`, and it must stay extractable (see its
  CLAUDE.md).

Both have the standard Makefile targets, `compose.yaml`, `.env.example`, `.dockerignore` and a
CLAUDE.md, and follow the service convention below. Fix a template in `templates/<kind>/`, so
every future service gets the fix.

## The service convention (what every service must provide)

- **Makefile targets, same names everywhere:** `install`, `lint`, `format`, `typecheck`, `test`
  (fast, no Docker where possible); `test-integration` (if the service has one), `build`, `up`,
  `down`, `logs`, `run` (on the host), `contract` (services that publish to `contracts/`);
  service-specific extras (e.g. `migrate`, `seed-db`, `api-types`). The same shell header, the
  `require-no-dev-stack` guard on `build`/`up`, and a `help` target.
- **`compose.yaml`:** `name: <svc>`, no `container_name`, no external networks; host ports as
  `${<SVC>_<THING>_PORT:-default}`; `env_file: [{path: .env, required: false}]`;
  container-network values (hostnames, internal ports) always go in `environment:`, which beats
  `env_file`.
- **Build context:** always the service directory, with a committed `.dockerignore`. It never
  builds from the repo root. A service that needs something from `contracts/` commits a
  generated copy of it (like web-plusdas's `src/api/generated/`), or uses a BuildKit named context.
- **Config:** read from the service's own `.env` (Python: pydantic-settings with `env_file`
  anchored via `Path(__file__)`; Node: runtime config at container start, never build-time env).
  Nothing reads a root `.env`.
- **CLAUDE.md sections:** Owns / Does not own · Commands (the standard targets) · Contracts
  provided/consumed · Gotchas. About 150 lines or less; deep reference material goes in `docs/`
  or a service skill.
- **Port registry:** in the root CLAUDE.md and `.env.example`, kept in sync.

## Before starting

- **Name:** lowercase kebab-case, starting with a letter (it's also the compose project name,
  the compose service name and, with `-` → `_`, the Python package / the env prefix).
- **Port:** take it from the port registry in the root `CLAUDE.md`. Reserved: optimizer 8010,
  powerflow 8020. Taken: 5173/5174 by web-plusdas. A Node service takes two ports: `--port`
  for the container and the next one for its Vite dev server (`make run`). For anything else,
  ask the user and pick ports that aren't in the registry.
- **Dependencies:** the templates use only packages the repo already uses (Python: fastapi,
  uvicorn, pydantic-settings; dev: pytest, ruff, httpx. Node: react, react-dom; dev: the
  vite/typescript/eslint/vitest/openapi-typescript set web-plusdas uses). Ask the user before
  adding any other.

## Procedure — Python (from the repo root)

1. Generate the files:
   `uv run --no-project python .claude/skills/new-service/scaffold.py --name <name> --port <port> --description "<one line>"`
2. Lock and install: `cd services/<name> && uv lock && cd ../..`, then
   `make -C services/<name> install`.
3. Publish the contract: `make -C services/<name> contract`.
4. Register the service (see "Registration" below). `contracts/README.md` gets a row for
   `openapi/<name>.openapi.json` (provider `services/<name>`, consumers "none yet").
5. Fill in the TODO sections ("Owns", "Does NOT own") of `services/<name>/CLAUDE.md` with what
   the user said the service is for. Leave "Gotchas" as it is.

## Procedure — Node (from the repo root)

1. Generate the files:
   `uv run --no-project python .claude/skills/new-service/scaffold.py --kind node --name <name> --port <port> --description "<one line>"`
2. Lock and install: `cd services/<name> && npm install && cd ../..` (creates
   `package-lock.json` from the template's ranges; commit it).
3. Generate the API types: `make -C services/<name> api-types` (writes
   `src/api/generated/backend-ot.ts`; commit it).
4. Register the service (see "Registration" below), plus:
   - `deploy/compose/<name>.dev.override.yaml`, a copy of `web-plusdas.dev.override.yaml`
     (`API_UPSTREAM=http://backend-ot:8000`, `depends_on: backend-ot`), included next to the
     service's compose file in `dev.yaml` (`- path: [../../services/<name>/compose.yaml,
     <name>.dev.override.yaml]`);
   - `contracts/README.md`: add `services/<name>` to the Consumers of `openapi/backend-ot.openapi.json`,
     and the root `contracts` skill's consumer step (step 5) gets the same `make api-types` line
     as web-plusdas.
5. Fill in "Owns" in `services/<name>/CLAUDE.md`.

## Registration (both kinds; the only files outside the service it may touch)

- root `Makefile`: add `<name>` to `SERVICES`;
- `deploy/compose/dev.yaml`: include `../../services/<name>/compose.yaml` (Node: with its override);
- root `.env.example`: the registry comment, and `# <ENV_PREFIX>_HTTP_PORT=<port>`;
- root `CLAUDE.md`: the port registry and the services list;
- `.claude/skills/run-platform/SKILL.md`: "Default host ports";
- `contracts/README.md`: as described in the procedure.
- Service-specific skills go in `services/<name>/.claude/skills/<skill>/SKILL.md` once the
  service has a repeatable workflow of its own.

## Done when

- `make -C services/<name> lint typecheck test` passes.
- `make check-boundaries` passes and `make help` lists the service.
- `git add services/<name> contracts/` and then `make check` passes. (It includes
  `contracts-check`, which compares against the index.)
- `docker compose -f deploy/compose/dev.yaml config -q` is valid.
- Python: `make down` at the root, then `make -C services/<name> up` reports the container
  healthy, and `curl http://localhost:<port>/api/healthz` returns `{"ok":true}`. Then `make -C services/<name> down`.
- Node: root `make up`, then `make -C services/<name> test-integration` prints
  `RESULT: same-origin OK`.
