---
name: new-service
description: Create a new service in this monorepo (optimizer, powerflow, or any new Python/FastAPI service) scaffolded to the service convention and registered everywhere it must be. Use for "add a new service", "scaffold the optimizer", "create a powerflow service", "start a new microservice".
---

# Scaffold a new service

Creates `services/<name>/`: a FastAPI app in `src/<package>/` with `/api/healthz`, config via
pydantic-settings, a pytest suite, the standard Makefile targets, `compose.yaml`, a uv-based
Dockerfile, `.env.example`, `.dockerignore`, a CLAUDE.md, and an OpenAPI contract in
`contracts/openapi/<name>.openapi.json`. The convention it follows is "The service convention"
in `MONOREPO_ROADMAP.md`. The templates are in `templates/` next to this file. Change them there
so every future service gets the fix.

## Before starting

- **Name:** lowercase kebab-case, starting with a letter (it's also the compose project name,
  the compose service name and, with `-` → `_`, the Python package).
- **Port:** take it from the port registry in the root `CLAUDE.md`. Reserved: optimizer 8010,
  powerflow 8020, frontend 5173 (Node, not covered by these templates). For anything else, ask
  the user and pick one that isn't in the registry.
- **Dependencies:** the templates use only packages the repo already uses (fastapi, uvicorn,
  pydantic-settings; dev: pytest, ruff, httpx). Ask the user before adding any other.

## Procedure (from the repo root)

1. Generate the files:
   `uv run --no-project python .claude/skills/new-service/scaffold.py --name <name> --port <port> --description "<one line>"`
2. Lock and install: `cd services/<name> && uv lock && cd ../..`, then
   `make -C services/<name> install`.
3. Publish the contract: `make -C services/<name> contract`.
4. Register the service (these are the only files outside the service it may touch):
   - root `Makefile`: add `<name>` to `SERVICES`;
   - `deploy/compose/dev.yaml`: add `- path: ../../services/<name>/compose.yaml` under `include:`;
   - root `.env.example`: move the service from "reserved" to a real entry in the registry
     comment, and add `# <ENV_PREFIX>_HTTP_PORT=<port>`;
   - root `CLAUDE.md`: the port registry and the services list;
   - `contracts/README.md`: a row for `openapi/<name>.openapi.json` (provider `services/<name>`,
     consumers "none yet").
5. Fill in the TODO sections ("Owns", "Does NOT own") of `services/<name>/CLAUDE.md` with what
   the user said the service is for. Leave "Gotchas" as it is.
6. Service-specific skills go in `services/<name>/.claude/skills/<skill>/SKILL.md` once the
   service has a repeatable workflow of its own.

## Done when

- `make -C services/<name> lint test` passes.
- `make check-boundaries` passes and `make help` lists the service.
- `git add services/<name> contracts/` and then `make check` passes. (It includes
  `contracts-check`, which compares against the index.)
- `make down` at the repo root, then `make -C services/<name> up` reports the container healthy
  (a service's `up` refuses while the root dev stack runs).
  `curl http://localhost:<port>/api/healthz` → `{"ok":true}`. Then `make -C services/<name> down`.
- `docker compose -f deploy/compose/dev.yaml config -q` is valid.
