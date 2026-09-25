---
name: run-platform
description: Run, start, stop, reset, seed or check the PAE platform services locally — the whole dev stack from the repo root (the default for development), or one service on its own. Use for "bring up the stack", "restart everything", "run backend-ot against the mock", "is the backend polling?", "start mock-modbus on its own", "port is already in use", "dev stack is running" errors, or before verifying a change end-to-end.
---

# Run the platform locally

**The repo root takes priority.** Development normally happens with the whole platform, started
from the root. Running a single service on its own is the exception.

| Mode | Command | Behaviour |
|---|---|---|
| **Dev stack** (default): all services on one network | `make up` at the root (or `make up svc=backend-ot` for one service plus its deps) | **Reset:** first stops every platform container (the dev stack *and* any service started on its own), then builds, starts and waits until healthy. Services find each other by compose name (`mock-modbus:502`) |
| **One service alone** (exception) | `make down` at the root first, then `make -C services/<svc> up` | A service's `up` / `up-build` / `build` **refuses** while the dev stack (`pae-dev`) runs. Standalone backend-ot reads Modbus from `host.docker.internal:502`, so a standalone mock-modbus pairs with it |

- Root `make down` stops every platform container in both modes. Data volumes are kept.
- Root `make down-all` (DESTRUCTIVE) also deletes every platform stack's volumes (postgres and
  redis data), images (built and pulled) and networks; the next `make up` re-pulls, rebuilds and
  starts from empty databases (then `make seed`). **Only run it when the user asks for it.**
  Each service also has its own `make -C services/<svc> down-all`.
- Only the platform's own compose projects are touched: `pae-dev` and each service's project.
  Other Docker containers, and the integration-test stacks `backend-ot-test-*`, never are.
- Root `make up`/`make down` **will stop services the user started on their own**. That's the
  intended rule, but if `docker compose ls` shows standalone stacks you didn't start, tell the
  user before running it.

mock-modbus is **DEV-ONLY**. It's in the dev stack and in its own directory, never in a
production manifest.

## Default host ports (the registry in the root CLAUDE.md)

backend-ot http **8000**, postgres **5435**, redis **6380** · mock-modbus **502**. Override them
only when something *outside* the platform holds a port:
- Dev stack: in the root `.env` (copy `.env.example`), or in the shell.
- One service alone: in the shell, e.g. `BACKEND_OT_HTTP_PORT=18000 make -C services/backend-ot up`.
- Variables: `BACKEND_OT_HTTP_PORT`, `BACKEND_OT_POSTGRES_PORT`, `BACKEND_OT_REDIS_PORT`,
  `MOCK_MODBUS_PORT`; standalone backend-ot's Modbus target: `BACKEND_OT_AGGREGATOR_HOST` /
  `BACKEND_OT_AGGREGATOR_PORT`.

"Port is already allocated" after a root `make up` means something *outside* the platform holds
it: `docker ps --format "{{.Names}} {{.Ports}}"`. Ask the user before stopping anything that
isn't a platform project; otherwise override the port.

## Procedure — whole platform (default)

1. Docker must be running: `docker info` (on Windows, start Docker Desktop if it fails).
2. `make up` resets and starts everything, then waits until every container is healthy.
3. `make seed` loads backend-ot's dev site. Its devices and points are built from mock-modbus's
   published contract (`contracts/modbus/mock-modbus.devices.json`); it's idempotent.
4. `make e2e` waits for polling, then checks every seeded point reads inside the range
   mock-modbus declares for it. Expect `RESULT: AGREE` for all 3 mock devices.
5. Inspect with `make ps`, `make logs svc=backend-ot`, and `curl localhost:<http port>/api/healthz`.
6. Stop with `make down`. The dev stack's data volumes are separate from the standalone stacks'.

## Procedure — one service alone

1. `make down` at the root. Otherwise the service refuses with "the platform dev stack
   (pae-dev) is running".
2. mock-modbus only: `make -C services/mock-modbus up`, then `make -C services/mock-modbus logs`.
3. backend-ot against a standalone mock: start mock-modbus first, then
   `make -C services/backend-ot up-build`, `make -C services/backend-ot seed-db`, and `make e2e`
   at the root (it reads `localhost:<BACKEND_OT_HTTP_PORT or 8000>`).
4. Stop each with `make -C services/<svc> down`, or all at once with root `make down`.

## Without Docker (fast inner loop)

`make test` (all services) needs no containers. `make -C services/mock-modbus run` starts
the simulator on host port 5020. `make -C services/backend-ot run` needs a reachable
postgres + redis (e.g. from its standalone stack) and uses `services/backend-ot/.env`.

## Done when

`make ps` shows every container healthy and `make e2e` prints `RESULT: AGREE`, or the same
check agrees against a standalone backend-ot. Tear down what you started.
