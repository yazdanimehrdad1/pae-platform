---
name: run-platform
description: Run, start, stop, seed or check the PAE platform services locally — the whole dev stack (every service on one network) or one service standalone, including side-by-side runs with custom host ports. Use for "bring up the stack", "run backend-ot against the mock", "is the backend polling?", "start mock-modbus", "run it next to my other stack/worktree", "port is already in use", or before verifying a change end-to-end.
---

# Run the platform locally

Two ways to run, both built from each service's own `compose.yaml`:

| Mode | Command (from repo root) | How services find each other |
|---|---|---|
| **Dev stack** — all services, one network | `make up` (or `make up svc=backend-ot`) | compose service names (`mock-modbus:502`, `backend-ot-postgres:5432`) |
| **Standalone** — one service's own stack | `make -C services/<svc> up` | backend-ot reaches mock-modbus's *host* port via `host.docker.internal` |

mock-modbus is **DEV-ONLY**. It's in the dev stack and in its own directory, never in a
production manifest.

## Default host ports (the registry in the root CLAUDE.md)

backend-ot http **8000**, postgres **5435**, redis **6380** · mock-modbus **502**.
Every one can be overridden, which is how several stacks run at once:

- **Dev stack:** put overrides in the root `.env` (copy `.env.example`), or set them in the shell.
- **Standalone:** set them in the shell only, e.g.
  `BACKEND_OT_HTTP_PORT=18000 BACKEND_OT_POSTGRES_PORT=15435 BACKEND_OT_REDIS_PORT=16380 make -C services/backend-ot up`.
- Variables: `BACKEND_OT_HTTP_PORT`, `BACKEND_OT_POSTGRES_PORT`, `BACKEND_OT_REDIS_PORT`,
  `MOCK_MODBUS_PORT`. For standalone backend-ot's aggregator target:
  `BACKEND_OT_AGGREGATOR_HOST` / `BACKEND_OT_AGGREGATOR_PORT` (default `host.docker.internal:502`).

"Port is already allocated" means another stack holds it: `docker ps --format "{{.Names}} {{.Ports}}"`,
then pick free ports. Never stop or remove containers you didn't start without asking the user.

## Procedure — whole platform

1. Docker must be running: `docker info` (on Windows, start Docker Desktop if it fails).
2. `make up` builds and starts everything and waits until every container is healthy.
3. `make seed` loads backend-ot's dev site. Its devices and points are built from mock-modbus's
   published contract (`contracts/modbus/mock-modbus.devices.json`); it's idempotent.
4. `make e2e` waits for polling, then checks every seeded point has a reading inside the
   range mock-modbus declares for it. Expect `RESULT: AGREE` for all 3 mock devices.
5. Inspect with `make ps`, `make logs svc=backend-ot`, and `curl localhost:<http port>/api/healthz`.
6. Stop with `make down` (volumes are kept; the dev stack's data is separate from the standalone stacks').

## Procedure — one service standalone

- mock-modbus only: `make -C services/mock-modbus up`, then `make -C services/mock-modbus logs`.
- backend-ot against a standalone mock: start mock-modbus first, then
  `make -C services/backend-ot up-build`, `make -C services/backend-ot seed-db`, and
  `uv run --no-project python scripts/e2e/check_backend_reads_mock.py --api http://localhost:<http port>/api`.
- Stop each with `make -C services/<svc> down`.

## Without Docker (fast inner loop)

`make test` (all services) needs no containers. `make -C services/mock-modbus run` starts
the simulator on host port 5020. `make -C services/backend-ot run` needs a reachable
postgres + redis (e.g. from its standalone stack) and uses `services/backend-ot/.env`.

## Done when

`make ps` shows every container healthy and `make e2e` prints `RESULT: AGREE`, or for a
standalone run the e2e script agrees against that stack's port. Tear down what you started.
