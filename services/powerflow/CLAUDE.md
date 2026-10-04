# powerflow

Grid-connected microgrid power flow simulator (pandapower). It stands in for a real site for EMS
development: the EMS writes setpoints, the simulator applies the asset limits, solves the network
every step in real time, and publishes measurements. README.md has the models, API, config and
sign conventions.

**Owns**
- The sites, in its own Postgres (the only store; `SiteConfig` in `src/powerflow/site_config/` is the schema). A fresh database gets the default sites from the data migration `storage/migrations/0003_default_sites.sql`; they are category `default` (`0004`), editable but not deletable. Sites created through the API are `custom`. The load/PV profile scenarios are CSV files in `profiles/`. All of it is reachable through the API.
- The asset models: BESS SOC and limits, PV curtailment and PF, load profiles with noise.
- The network and its solver (pandapower, Newton-Raphson).
- The real-time simulation engine and its in-memory measurement history.
- The protocol-neutral point lists (`src/powerflow/points/`): HTTP, history and PointRegistry names.
- The PAE point standard (`docs/point-standard/*.csv`) and the Modbus TCP server that serves it (`src/powerflow/point_standard/` maps and calculates every point; `interfaces/modbus/` serves the image).
- The HTTP API under `/api`.

**Does NOT own**
- EMS logic.
- Real device polling: backend-ot does that.
- The Modbus simulator for backend-ot: that's mock-modbus.
- Anything outside its own Postgres. Measurement history is RAM-only.
- Dynamics, protection, unbalanced models and islanding (non-goals for now).

## Commands
Run from the repo root as `make -C services/powerflow <target>` (or `make <target>` here).
Same Makefile on Windows (recipes run in Git for Windows' sh). `make help` lists all.
- **Setup:** `make install` (uv sync → `.venv`). Add deps with `uv add` / `uv add --dev`, after asking the user.
- **Gates:** `make lint` (ruff) · `make format` · `make typecheck` (pyright, blocking) · `make test` (pytest, no Docker, ~45 s; the 24 h SOC test is the slow one).
- **`make run`:** the API on the host at http://127.0.0.1:8020/api/health (docs at `/docs`).
- **`make test-integration`:** runs the Postgres tests in a throwaway compose project.
- **`make profiles`:** regenerates the profile CSVs.
- **`make up` / `down` / `logs`:** a standalone container on `POWERFLOW_HTTP_PORT` (default 8020). `up`/`build` refuse while the root dev stack runs.

## Contracts
- **Provides:** `contracts/openapi/powerflow.openapi.json` (consumed by web-plusdas), `contracts/powerflow/points.json` and `contracts/modbus/powerflow.registers.json` (the Modbus server's register layout), all written by `make contract`. Contract versions: `API_VERSION` in `src/powerflow/app.py`, `POINTS_CONTRACT_VERSION` and `REGISTERS_CONTRACT_VERSION` in `src/powerflow/contract.py`. `make test` fails while any is stale (`tests/test_contract.py`).
- **Consumes:** none. Consume other services only through `contracts/` and the network, never their code or files.

## Layout (dependencies point inward)
- **`interfaces/`** (http; modbus = read-only aggregator over `point_standard/`; dnp3 is a placeholder README) → **`point_standard/`** (CSV layout, yes/calc resolvers) → **`core/`** (engine, step + energy counters, state store, SetpointService, PointRegistry, SiteLibrary) → **`points/`**, **`storage/`** (repositories, migrations, profile files) → **`models/`**, **`network/`**, **`profiles/`**, **`site_config/`**.
- **`models/` is pure:** no pandapower, no clock.
- **`network/pandapower_solver.py`** is the only module that imports pandapower, behind `PowerFlowSolver`.
- **`core/step.py` is a pure function:** time and setpoints are passed in, which is what makes runs deterministic.
- **Adapters** use only `AdapterContext` (engine, PointRegistry, SetpointService). Every setpoint, from any protocol, goes through `SetpointService`.

## Conventions
- Code lives in the `powerflow` package under `src/`, with absolute imports.
- **Service settings:** only `src/powerflow/settings.py` (pydantic-settings; `DATABASE_URL`, `PROFILES_DIR`, `POINT_STANDARD_DIR`, `ACTIVE_SITE`, `LOG_LEVEL`, `MODBUS_HOST`, `MODBUS_PORT`, `MODBUS_UNIT_ID`). compose pins the container's Modbus, path and `ACTIVE_SITE` values so a host `.env` can't leak in.
- **Configuration:** sites (`SiteConfig`, `extra="forbid"`, stored with every field) and the active site live in Postgres, behind `storage.ConfigRepository`. There are no site files: the default sites are a data migration, and `storage/seed_data.py` reads it for tests and the Postman example only.
  - Production uses `PostgresConfigRepository`; unit tests use `InMemoryConfigRepository`. `tests/repository_contract.py` runs against both.
  - Profile scenarios are still CSV files, in `storage.ProfileStore`.
  - Changing a default site for everyone = a new migration (applied migrations never re-run).
  - Validation happens before any write, in `core.SiteLibrary`.
  - Schema changes are new SQL files in `src/powerflow/storage/migrations/` (applied in order at startup). Never edit an applied migration.
- Pydantic models for every request/response; every route declares `response_model`.
- Point names (`<asset_type>.<asset_id>.<point>`) are the shared vocabulary. A measurement point's name is the field name on the snapshot model, so add both together; `test_points.py` checks that every point resolves.
- Every feature or fix ships with tests, and `make lint typecheck` stays clean.

## Gotchas
- **Point standard CSVs drive the Modbus server:** a new `yes`/`calc` value in the `powerflow_server` column needs a resolver in `point_standard/values.py` or `calc.py`, and vice versa (`test_point_standard.py` checks both ways). Rows are packed in CSV order, so inserting a row mid-file moves every later address: append instead. Any CSV change means `make contract`; a moved offset is a breaking change to the registers contract (bump `REGISTERS_CONTRACT_VERSION`).
- **Modbus port:** tests run the server on an ephemeral loopback port (autouse fixture in `conftest.py`). A host `make run` binds `MODBUS_PORT` (502), which mock-modbus also uses while the dev stack is up.
- **Grid impedance:** in pandapower, `ext_grid`'s `s_sc_max_mva`/`rx_max` only affect short-circuit studies. The power flow sees the grid strength through an explicit impedance element (see `network/topology.py`).
- **Site losses:** transformers plus collector feeders. They exclude the grid equivalent and the POI line, which are on the utility side of the POI meter.
- **`step_id` is the sim tick:** a real-time overrun skips ticks, so ids can have gaps and the skipped time is integrated as one longer step.
- **Non-convergence** keeps the last good snapshot (`converged=false`) and doesn't advance SOC.
- **Uploaded profiles:** a scenario saved with PUT keeps each asset's configured `scale`/`loop`, and hot-reloads into active-site assets even while running.
- **Tests never write the repo's `profiles/`:** anything that writes uses the `profiles_copy` fixture (a tmp copy). App tests use `InMemoryConfigRepository.with_default_sites()` (what a migrated database holds).
- **Container data** lives on volumes, not in git: `powerflow-postgres-data` for the sites and the active site, and `powerflow-profiles` for the profile CSVs. `make down-all` (and root `make down-all`) deletes them; the next start migrates a fresh database (the default sites).
- **Host `make run` needs Postgres** on `DATABASE_URL` (default localhost:5436).
- **Interfaces follow the config:** `AdapterRegistry.reconcile` (wired as `SiteLibrary.on_config_replaced`) restarts the protocol adapters after every config change (activate, saving the active site). A failed start is reported in `/api/health`, not raised.
- **`seed` must be ≥ 0:** it's a numpy SeedSequence. Load noise is keyed on (seed, step).
