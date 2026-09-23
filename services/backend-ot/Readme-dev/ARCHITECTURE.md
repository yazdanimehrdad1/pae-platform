# Architecture

How this service is actually laid out. For the working agreement (commands, lint rules,
gotchas) see `CLAUDE.md` at the repo root.

## Layout

`src/` is a **flat** set of top-level modules, not a package. Everything imports as
`from config import ...`, `from db.connection import ...` — which is why `PYTHONPATH=src`
is required and bare `pytest` / bare `python main.py` fail.

```
src/
  app.py          FastAPI factory: lifespan (redis → db → scheduler), middleware, routers
  main.py         uvicorn entrypoint (reload=True is hardcoded)
  config.py       pydantic-settings Settings; the only place env is read
  constants.py    fixed protocol constants (not env-driven)
  logger.py       stdlib console logging to stdout
  api/
    routers/      HTTP surface, all mounted under /api by app.py
    controllers/  request → helper orchestration for devices and sites
    middleware/   validate_time_range, runs on every request
  db/             connection/session management + per-table query modules
  schemas/
    api_models/   request/response pydantic models + shared type aliases
    db_models/    SQLAlchemy ORM models (orm_models.py)
    internal_models.py
  helpers/        the business logic: device_points, modbus, reads, sites, workers
  services/
    modbus/       pymodbus client wrapper
    server_sent_events/  live-stream session plumbing
  scheduler/      APScheduler engine + Redis leader election / job locks
  cache/          Redis client and the /api/cache admin surface
  utils/          AppError hierarchy
```

## Request and poll paths

**HTTP:** router → controller or helper → `db/` module → SQLAlchemy session. Routers stay
thin; `utils/exceptions.AppError` subclasses carry the HTTP status they map to.

**Polling:** `scheduler/engine.py` registers the `modbus_poll` job at
`POLL_INTERVAL_SECONDS`. Redis leader election means exactly one replica polls. The job
reads its targets from the DB (sites → devices → device points), and
`helpers/modbus/poll_device.py` turns each device's `scan_ranges` into Modbus reads,
chunked at `MODBUS_MAX_REGISTERS_PER_READ` (125). Results land in `device_points_readings`.

`scan_ranges` is derived, not authored: `helpers/device_points/scan_range_computation.py`
clusters a device's NATIVE points into contiguous ranges per `poll_kind`
(`holding` / `input` / `coils`), and point CRUD recomputes it unless
`devices.scan_ranges_locked` is set.

## Data

Postgres via asyncpg + SQLAlchemy 2.0 async. Tables: `sites`, `devices`, `device_points`,
`device_points_readings`, `schema_migrations`.

Migrations are raw numbered SQL under `src/db/migrations/NNN_*.sql`, applied in glob order
by `scripts/migrate_db.py` and tracked in `schema_migrations`. **There is no Alembic** —
to change the schema, add the next `NNN_*.sql`.

Note the image is `timescale/timescaledb`, but no migration calls `create_hypertable`, so
the time-series tables are currently plain Postgres. Partitioning, compression and
retention are unimplemented.

## Known gaps

- No auth layer — every endpoint is unauthenticated.
- Redis is used for scheduler locks and an admin CRUD surface only; the poll and read
  paths do not cache.
- `GET /api/csv-exports/raw-register-map-csv` returns headers only — it has no data path.
