# Integration tests

Drive the real FastAPI app in-process (httpx `ASGITransport`, no uvicorn, no lifespan, so
the scheduler never starts) against a real Postgres and Redis.

## Running

```
make test-integration                     # Windows: .\make.ps1 test-integration
make test-integration TEST_PATH=tests/integration/api/routers/test_sites.py
.\make.ps1 test-integration tests/integration/api/routers/test_sites.py
```

This starts the throwaway stack in `docker-compose.test.yaml` (project
`pae-backend-ot-test`: postgres + redis in tmpfs, no host ports), migrates it, runs pytest,
then tears it down. The dev stack and its data are never touched. You don't need
`make up` first.

Every test starts from empty tables and an empty Redis (the autouse `reset_state` fixture
in `conftest.py`). That fixture refuses to run unless `INTEGRATION_DB_RESET_ALLOWED=1`,
which only the test stack and CI set. Anywhere else these tests are **skipped**, so a bare
`pytest tests/` can't wipe a dev database.

## Layout: mirrors `src/`

```
tests/integration/
  conftest.py        reset_state (autouse), client, db fixtures
  factories.py       payload builders + create-via-API helpers + insert_reading
  api/routers/       one test_<router>.py per src/api/routers/<router>.py
```

Arrange state through the public API (`factories.create_site` etc.) so tests use the same
write path as a real client. Use the `db` fixture + raw SQL only for data the API can't
create, such as readings.

## Known bugs (strict `xfail`)

A test that exposes a bug asserts the *correct* behavior and is marked
`xfail(strict=True, reason="BUG: ...")`. When the bug is fixed the test XPASSes, which fails
the run, so you remove the marker in the same change. There are none open right now.

## Coverage

### Done: API routers (`src/api/routers/`)
- [x] sites: CRUD, name uniqueness, soft/hard delete + restore cascade, comprehensive view
- [x] devices: CRUD, site scoping, standardized points on create, soft/hard delete + restore
- [x] device_points: bulk upsert, category filter, update, soft/hard delete + restore,
      scan-range recompute and manual lock/reset
- [x] device_points_readings: latest, timeseries order/limit/window, enum translation,
      display tz, query validation (endpoint + `validate_time_range` middleware)
- [x] health: healthz, readyz, db_health, redis_health, unreachable-device probe
- [x] cache: set/get/exists/delete, value types, TTL, pattern listing, clear
- [x] csv_exports: header-only template, unsupported type

### Waiting on the mock Modbus server
Add it as a service in `docker-compose.test.yaml`, then:
- [ ] `/health_modbus_client` and a *reachable* device in `/healthz/site/...`
- [ ] `live_stream_raw_registers` (SSE stream / resume / stop / sessions) and
      `live_stream_register_snapshot`
- [ ] Polling pipeline (`helpers/modbus/`, `helpers/workers/device_poll.py`): poll, decode,
      persist to `device_points_readings`, including scan-range chunking above
      `MODBUS_MAX_REGISTERS_PER_READ`

### Not yet covered
- [ ] Redis cache internals (`cache/cache.py`): reconnection, concurrent operations
