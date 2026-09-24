# pae-backend-ot

Owns: polling Modbus TCP devices (SEL RTACs) on a schedule and storing their
register/point readings as time-series in TimescaleDB, plus the sites → devices →
device-points CRUD, live register streaming, and CSV export API (all under `/api`).
Does NOT own: the upstream Modbus aggregator/RTAC itself (external, `AGGREGATOR_MODBUS_HOST`),
the DAS data-acquisition API (`pae-das-api`), or any downstream dashboard/analytics.

## Python setup — read this
- **uv only.** Deps are pinned in `uv.lock`; `make install` = `uv sync --frozen`. Add deps with
  `uv add` / `uv add --dev` (dev tools live in the `[dependency-groups] dev` group, never shipped
  in the image). The Dockerfile installs from the lock with `uv sync --frozen --no-dev`.
- Divergences from the global Python rules: types are checked with **mypy, not pyright**
  (`make typecheck`, not yet blocking); formatting is **black + ruff** (line-length 100).
- Imports are flat — modules import as `from config import ...`, `from db.connection import ...`,
  NOT a package. pytest gets `src` via `pythonpath` in pyproject, so plain `uv run pytest` works;
  other entry points (`scripts/*.py`, the image) put `src` on the path themselves.
- There is no auth layer at all yet; every endpoint is unauthenticated. `/api/healthz`
  must stay that way — the Docker HEALTHCHECK and k8s probes hit it.

## Commands
Run from the repo root as `make -C services/backend-ot <target>` (or `make <target>` in this
directory). Same Makefile on Windows — it runs recipes in Git for Windows' sh. `make help` lists all.
- Setup: `make install` (uv sync → `.venv`).
- Unit tests: `make test` — host, no Docker. Narrow with `make test TEST_PATH=tests/unit/helpers/modbus`.
- Integration tests: `make test-integration [TEST_PATH=...]` — throwaway postgres + redis
  (`compose.test.yaml`, project `backend-ot-test-<worktree dir>`, tmpfs, no host ports), migrates
  from zero, runs `tests/integration`, tears down. Never touches the dev stack; parallel worktrees
  don't collide. `make test-all` = both.
- Lint / format / types: `make lint` (ruff, CI-enforced) · `make lint-fix` · `make format` (black + ruff) · `make typecheck` (mypy).
- Standalone stack (Docker, `compose.yaml`): `make up` / `make up-build` (postgres, redis, app;
  migrations auto-run in the entrypoint) · `make down` · `make logs` · `make seed-db` ·
  `make apply-migration`. Reads the Modbus aggregator at `host.docker.internal:502` (a standalone
  mock-modbus). The whole platform together: `make up` / `make seed` / `make e2e` at the **repo
  root** (see the `run-platform` skill). Compose service names: `backend-ot`, `backend-ot-postgres`,
  `backend-ot-redis`.
- Run on the host: `make run` (needs pg+redis reachable) · `make migrate`.
- Schema changes: use the `add-migration` skill. API changes: use the `add-endpoint` skill.
- Checks: the root `test-runner` agent runs lint/tests and reports only failures.

## Contracts (rules: `contracts/README.md`, procedure: root `contracts` skill)
- **Provides** `contracts/openapi/backend-ot.openapi.json`: `make contract` regenerates it, and
  `make test` fails while it is stale (`tests/unit/test_contract.py`). The contract version is
  `version=` in `create_app()` (`src/app.py`). No consumers yet.
- **Consumes** `contracts/modbus/mock-modbus.devices.json` (dev seed only): seed devices and points
  are built from it (`tests/seed_db/mock_modbus_seed.py`). Never hand-edit seeded devices or points.
  Change the mock and run `make -C services/mock-modbus contract`.

## The feature comes first; tests prove it
The feature is the priority. Build it to the highest standard first — correct behavior,
correct HTTP status codes and error types, clean layering, the conventions in this file —
and *then* write unit and integration tests that prove it works as intended.
- Tests describe the behavior the feature **should** have. Never shape a test (or an
  assertion) around what the code happens to do today.
- If a test exposes a defect, fix the feature — don't weaken the test to pass. A strict
  `xfail` is only for a defect that is genuinely out of scope for the current change, and
  must be called out to the user.
- A green suite over a sub-standard feature is not done. Passing tests are the proof, not
  the goal.

## Typing: Pydantic models, not dicts — everywhere, including tests
Structured data is always a Pydantic model. This applies to app code, unit tests,
integration tests, and seed/mock data alike.
- **Reuse before you define.** Request/response bodies, payloads, and results use the models
  in `src/schemas/` (`api_models/`, `internal_models.py`, `modbus_models/`, …). Only define a
  new model when none fits.
- **All models live under `src/schemas/`.** A model used *only* by unit/integration tests or
  the seeder goes in `src/schemas/tests_models/<topic>.py` (re-exported from its
  `__init__.py`). App code (`api/`, `db/`, `helpers/`, `services/`, `scheduler/`) never
  imports `schemas.tests_models`. When an endpoint gains a real `response_model`, move its
  model to `schemas/api_models/` and delete the test-only copy.
- **No `Any`, no bare `dict`/`list`** for structured data. Precise generics are fine only
  for true lookup maps (e.g. `dict[str, Site]`, `dict[str, str]` enum labels).
- **Every route declares a `response_model`.** (Legacy exceptions today: `/cache/*` except
  get, `/readyz`, `/redis_health`, `/db_health` — their test-only mirrors are in
  `schemas/tests_models/api_responses.py`.)
- **In tests:** build requests with the model (`SiteCreateRequest(...)`, the
  `integration.factories` builders) and send `model.model_dump(mode="json")`
  (`exclude_unset=True` for partial updates); parse every response with
  `Model.model_validate(response.json())` or a `TypeAdapter(list[Model])`, then assert on
  attributes (`site.site_id`), never `response.json()["site_id"]`. The one exception is a
  deliberately invalid payload for a 4xx test — dump a valid model and override the bad
  field (`valid.model_dump(mode="json") | {"name": ""}`) so the corruption is explicit.
- Validate raw input with `Model.model_validate(raw)`, not `Model(**raw)`.

## Unit tests are required for every feature and bug fix
Every new feature, behavior change, or bug fix ships with unit tests **in the same change**.
A change is not done until `make test` passes and `make lint` is clean.
- **Layout mirrors `src/`:** tests for `src/<path>/<module>.py` live in
  `tests/unit/<path>/test_<module>.py` — e.g. `src/helpers/modbus/poll_device.py` →
  `tests/unit/helpers/modbus/test_poll_device.py`. Create missing folders as needed.
- **Every test folder needs an `__init__.py`.** Without it pytest puts `tests/unit/` on
  `sys.path` and `tests/unit/helpers/` shadows `src/helpers/`.
- **Shared test data** lives in plain modules under `tests/unit/` (e.g.
  `tests/unit/data_type_fixtures.py`), imported as `from unit.data_type_fixtures import ...`.
- **No I/O in unit tests** — no DB, redis, network, or real clock. Pass fakes in or patch at
  the boundary. Anything that needs postgres/redis belongs in `tests/integration/`.
- **Bug fixes include a regression test** that fails without the fix.
- Cover the invariant, not just the happy path: rejected inputs, edge cases, and the
  "these two lists must not drift apart" checks (see `tests/unit/helpers/modbus/`).
- Group tests in `Test*` classes per behavior, with a module docstring saying what
  invariant the file guards. Test code follows the same ruff rules as `src/`.

## Integration tests are required for API changes
Any new or changed endpoint (`src/api/routers/`) ships with integration tests in
`tests/integration/api/routers/test_<router>.py` **in the same change**, and a change touching
the API isn't done until `make test-integration` passes too. See `tests/integration/README.md`.
- **Same layout rules as unit tests:** mirror `src/`, `__init__.py` in every folder, shared
  helpers in plain modules imported as `from integration.factories import ...`.
- **Use the fixtures in `tests/integration/conftest.py`:** `client` (httpx AsyncClient on
  a fresh app; lifespan/scheduler not run) and `db` (raw asyncpg connection). The autouse
  `reset_state` truncates all tables + flushes redis before each test, so tests are
  independent. Never add a test that depends on another test's data.
- **Arrange through the API** (`factories.create_site/create_device/upsert_points`). Use raw
  SQL via `db` only for what the API can't create (e.g. `factories.insert_reading`).
- **Assert status codes and response bodies**, and cover the error paths (404/409/400/422),
  not just the happy path. Bodies are parsed into Pydantic models first (see "Typing:
  Pydantic models, not dicts"); AppError bodies parse as `schemas.tests_models.ApiErrorResponse`.
- **Found a bug while writing a test?** Fix the feature (see "The feature comes first").
  Only if the fix is out of scope: assert the *correct* behavior, mark it
  `@pytest.mark.xfail(strict=True, reason="BUG: ...")`, and tell the user. Never weaken the
  assertion to match the bug. Remove the marker in the change that fixes it (strict XPASS
  fails the run).
- **Safety guard:** tests only run when `INTEGRATION_DB_RESET_ALLOWED=1` (set by
  `compose.test.yaml` and CI); otherwise they skip. Never set it against a real DB.
- **Anything needing Modbus** (polling, live stream, `/health_modbus_client`) waits for the
  mock Modbus server (`services/mock-modbus`), to be added as a service in `compose.test.yaml`.

## Linting is CI-enforced — every change must leave `ruff check` clean
`make lint` (`ruff check src tests`) is the gate; the service's old `.github/workflows/ci.yml`
is inert in the monorepo until root CI exists, but treat any ruff error as blocking. Before finishing any Python
change, make sure ruff passes with zero errors. Config lives in `pyproject.toml` under
`[tool.ruff.lint]` (line-length 100; rule sets `E,W,F,I,B,C4,UP`; `E501`/`B008` ignored).
Concretely, write code that already satisfies these:
- **Modern typing (UP):** use built-in generics and unions — `list[int]`, `dict[str, X]`,
  `X | None` — NOT `typing.List`/`Dict`/`Optional`/`Union`. Don't import those from `typing`.
- **Sorted imports (I001):** stdlib → third-party → first-party, each group alphabetized.
- **Exception chaining (B904):** inside an `except`, always chain — `raise HTTPException(...)
  from err` when the caught exception is meaningful, or `... from None` for a deliberate
  translation (e.g. converting a lookup miss to a 404). Never a bare `raise X(...)` in `except`.
- **No trailing/blank-line whitespace (W29x)**, files end with a newline, no unused imports (F401).
- If a rule genuinely shouldn't apply, add a scoped `# noqa: <CODE>` with a reason — don't
  broaden the global ignore list without asking.
- Run `make lint` (check) and `make lint-fix` (auto-fix imports/typing/whitespace; B904 must
  be fixed by hand). ruff comes from `uv.lock`, so the version is the same everywhere.
- The monorepo-root pre-commit hook (`make hooks` enables it) runs this lint when backend-ot has staged changes.

## What this service owns
- Postgres tables: `sites`, `devices`, `device_points`, `device_points_readings`,
  `schema_migrations`. Migrations were squashed on 2026-09-22 into a 4-file baseline
  (`001`–`004`, one per table); the old `device_register_map`, `*_configs`,
  `register_readings_raw` and `register_readings_translated` tables no longer exist — don't
  reference them. No `create_hypertable` call exists in any migration, so these are plain
  Postgres tables despite the TimescaleDB image.
- Redis: APScheduler leader-election / job locks, plus a `/api/cache` admin CRUD surface
  (not a message bus). The poll and read paths do NOT use the cache — it is not read-through.
- Publishes no events to any broker; there is no DAS API integration.

## Gotchas
- Host ports are remapped: app 8000, **postgres 5435→5432, redis 6380→6379** (override with
  `BACKEND_OT_HTTP_PORT` / `_POSTGRES_PORT` / `_REDIS_PORT` in the shell). A local `.env` for
  host-run tools must target those host ports; inside containers compose sets the internal ones.
- Migrations are raw numbered SQL in `src/db/migrations/NNN_*.sql`, applied and tracked in
  `schema_migrations` by `scripts/migrate_db.py`. No Alembic — add a new `NNN_*.sql` to change schema.
- Scheduler uses Redis leader election: only ONE replica polls (job `modbus_poll`, every
  `POLL_INTERVAL_SECONDS`, default 10). It won't start if Redis is down; `SCHEDULER_ENABLED=false`
  disables it. Polling targets are read from the DB (sites → devices → device-points).
- A global `validate_time_range` middleware (`src/api/middleware/`) runs on every request
  and rejects bad start/end query params.
- `main.py` hardcodes `reload=True`; the Dockerfile runs a single uvicorn process.
  There is no gunicorn config in this repo.

## Output style (keep token usage down)
- Keep responses short. Lead with the answer; no recap tables or restated diffs unless asked.
- Don't re-print file contents you just edited.
