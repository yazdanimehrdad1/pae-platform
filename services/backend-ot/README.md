# Modbus TCP FastAPI Microservice

A FastAPI-based REST API service for communicating with Modbus TCP servers using pymodbus.

## Features

- **GET /api/healthz**: Liveness check (no I/O; the Docker HEALTHCHECK and k8s probes hit it). `/api/readyz` checks postgres and redis
- Robust error handling with proper HTTP status codes
- Environment variable configuration
- Clean connection management (no socket leaks)
- **Distributed Scheduler**: APScheduler with Redis-based leader election for multi-replica Kubernetes deployments

## Scheduler Implementation

The service includes a distributed scheduler system for periodic Modbus polling and data storage jobs. **Step 1**: Added the APScheduler dependency to pyproject.toml for async job scheduling. **Step 2**: Configured scheduler settings in config.py including leader lock TTL, heartbeat interval, and pod identification. **Step 3**: Implemented Redis-based distributed locking system with leader election and per-job execution locks in scheduler/locks.py. **Step 4**: Created scheduler engine in scheduler/engine.py that wraps all jobs with lock verification before execution. **Step 5**: Integrated scheduler lifecycle into FastAPI app startup/shutdown hooks for automatic initialization and cleanup.

## Installation

This service lives in the `pae-platform` monorepo at `services/backend-ot`. Dependencies are
managed with **uv** and pinned in `uv.lock`; Make is the only entry point (on Windows too — the
Makefile runs its recipes in Git for Windows' sh). From the repo root:

```bash
make -C services/backend-ot install     # uv sync → services/backend-ot/.venv (incl. dev tools)
make -C services/backend-ot help        # every target
```

## Configuration

Settings are pydantic-settings fields in `src/config.py`, read from environment variables and
from `services/backend-ot/.env` (anchored to the service directory, so it loads the same way
from any working directory). Start from the template: `cp .env.example .env`.

- **Containers don't need a `.env`:** `compose.yaml` supplies dev defaults, and sets every
  container-network value (postgres/redis hostnames, internal ports, the Modbus target) in
  `environment:`, which wins over `.env`.
- **Host runs** (`make run`, `make migrate`) need `POSTGRES_PASSWORD` and must target the
  remapped host ports: postgres **5435**, redis **6380**.

The Modbus aggregator is `AGGREGATOR_MODBUS_HOST` / `AGGREGATOR_MODBUS_PORT` (host-run defaults
`localhost:502`; compose overrides them, see below).

## Running Locally

### The whole platform (recommended)

From the monorepo root, backend-ot runs next to the DEV-ONLY Modbus simulator
(`services/mock-modbus`) on one network, seeded with devices that match it. The root takes
priority: `make up` first stops every platform container, including services started on their
own, then starts everything fresh.

```bash
make up      # reset: stop all platform containers, build + start every service, wait until healthy
make seed    # load backend-ot's dev sites/devices/points (built from mock-modbus's contract)
make e2e     # check backend-ot polls mock-modbus and every value is in range
make down    # stop every platform container (data volumes are kept)
make down-all  # DESTRUCTIVE: also delete volumes (postgres/redis data), images and networks
```

### backend-ot standalone

Run `make down` at the repo root first: `up`/`up-build`/`build` refuse while the dev stack runs.

```bash
make -C services/backend-ot up          # postgres + redis + app; migrations run on start
make -C services/backend-ot seed-db     # dev data
make -C services/backend-ot health      # GET /api/healthz
make -C services/backend-ot logs        # follow the app's logs
make -C services/backend-ot down
```

Standalone, the app polls the Modbus aggregator at `host.docker.internal:502`, i.e. a
standalone mock-modbus (`make -C services/mock-modbus up`) or anything else listening on the
host. Point it elsewhere with `BACKEND_OT_AGGREGATOR_HOST` / `BACKEND_OT_AGGREGATOR_PORT`.

Host ports default to 8000 (API), 5435 (postgres), 6380 (redis); override them in the shell if
something else on your machine uses them, e.g.
`BACKEND_OT_HTTP_PORT=18000 BACKEND_OT_POSTGRES_PORT=15435 BACKEND_OT_REDIS_PORT=16380 make -C services/backend-ot up`.

### On the host (no app container)

With postgres and redis reachable (e.g. the standalone stack's containers) and a `.env` as
described above:

```bash
make -C services/backend-ot migrate     # apply SQL migrations
make -C services/backend-ot run         # uvicorn with reload, from src/
```

The API is at `http://localhost:8000/api`; Swagger UI at `http://localhost:8000/docs`.

### Tests and lint

```bash
make -C services/backend-ot test              # unit tests, no Docker
make -C services/backend-ot test-integration  # throwaway postgres + redis in Docker, then torn down
make -C services/backend-ot lint              # ruff (blocking)
```

## Docker Details

### Architecture Decision

**Single Container Approach:** The FastAPI service and Modbus client are kept in the same container because:
- The Modbus client is a Python library/module, not a separate service
- They share the same Python process - no network boundary needed
- Simpler deployment, debugging, and resource management
- Standard microservice pattern

### Image

`docker/Dockerfile`, built with the service directory as context (`make -C services/backend-ot
build`): dependencies are installed from `uv.lock` with `uv sync --frozen --no-dev`, the runtime
image runs as uid 999, and its entrypoint applies pending migrations before starting uvicorn.
The compose services are `backend-ot`, `backend-ot-postgres` and `backend-ot-redis`.

## Example curl Commands

### Health Check

```bash
curl http://localhost:8000/api/healthz
```

Response (from the dev stack; `host`/`port`/`device_id` echo the configured Modbus aggregator,
nothing is contacted):
```json
{"ok":true,"host":"mock-modbus","port":502,"device_id":1,"detail":"API is healthy"}
```

## Error Handling

The service translates Modbus errors into appropriate HTTP status codes:

- **400 Bad Request**: Invalid Modbus parameters or illegal function/data address
- **503 Service Unavailable**: Connection failures
- **504 Gateway Timeout**: Request timeouts
- **500 Internal Server Error**: Unexpected errors

Example error response:
```json
{
  "detail": "Illegal data address - The data address received is not valid"
}
```

## TODO

### Observability (not implemented)

The `src/telemetry/` package (tracing + metrics) and the `/api/metrics` router were
removed and still need to be re-implemented:

- [ ] **Tracing** — OpenTelemetry spans around Modbus polls, DB writes, and API requests,
      exported to an OTLP collector. Propagate trace context across the scheduler jobs.
- [ ] **Metrics** — Prometheus metrics + a `/api/metrics` scrape endpoint. At minimum:
      poll duration/success/failure counters per device, register read latency,
      device_points_readings write throughput, scheduler leader-election state.

### Other

- [ ] Persistent pooled client connections
- [ ] Batch polling multiple addresses
- [ ] Word/byte-order conversions for 32/64-bit values

## Testing with a Modbus Simulator

The monorepo ships one: `services/mock-modbus` (DEV-ONLY), which serves three simulated devices.
Run it together with backend-ot from the repo root (`make up && make seed && make e2e`, above), or,
after a root `make down`, standalone with a standalone backend-ot (`make -C services/mock-modbus up`).

