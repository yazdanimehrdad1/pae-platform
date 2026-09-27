# powerflow

Grid-connected microgrid power flow simulator (pandapower). It stands in for a real site for EMS
development: the EMS writes setpoints, the simulator applies the asset limits, solves the network
every step in real time, and publishes measurements. README.md has the models, API, config and
sign conventions.

**Owns**
- The site data in `site_config/`: site configs (N BESS / PV / loads; `SiteConfig` in `src/powerflow/site_config/` is the schema), per-site Modbus maps for every asset, load/PV profile scenarios, and generated schemas. All of it is reachable through the API (the schemas read-only).
- The asset models: BESS SOC and limits, PV curtailment and PF, load profiles with noise.
- The network and its solver (pandapower, Newton-Raphson).
- The real-time simulation engine and its in-memory measurement history.
- The protocol-neutral point lists (`src/powerflow/points/`) and the Modbus map format.
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
- **Gates:** `make lint` (ruff) · `make format` · `make typecheck` (pyright, blocking) · `make test` (pytest, no Docker, ~40 s; the 24 h SOC test is the slow one).
- **`make run`:** the API on the host at http://127.0.0.1:8020/api/health (docs at `/docs`).
- **`make test-integration`:** runs the Postgres tests in a throwaway compose project.
- **`make profiles`:** regenerates the profile CSVs.
- **`make modbus-maps`:** regenerates the *default* map files, and never touches the database. A test fails while those files differ from the generator.
- **`make up` / `down` / `logs`:** a standalone container on `POWERFLOW_HTTP_PORT` (default 8020). `up`/`build` refuse while the root dev stack runs.

## Contracts
- **Provides:** `contracts/openapi/powerflow.openapi.json` and `contracts/powerflow/points.json`, both written by `make contract`. Contract versions: `API_VERSION` in `src/powerflow/app.py` and `POINTS_CONTRACT_VERSION` in `src/powerflow/contract.py`. `make test` fails while either is stale (`tests/test_contract.py`).
- **Consumes:** none. Consume other services only through `contracts/` and the network, never their code or files.

## Layout (dependencies point inward)
- **`interfaces/`** (http implemented; modbus/dnp3 are placeholder READMEs) → **`core/`** (engine, step, state store, SetpointService, PointRegistry) → **`models/`**, **`network/`**, **`profiles/`**, **`site_config/`**.
- **`models/` is pure:** no pandapower, no clock.
- **`network/pandapower_solver.py`** is the only module that imports pandapower, behind `PowerFlowSolver`.
- **`core/step.py` is a pure function:** time and setpoints are passed in, which is what makes runs deterministic.
- **Adapters** use only `AdapterContext` (engine, PointRegistry, SetpointService). Every setpoint, from any protocol, goes through `SetpointService`.

## Conventions
- Code lives in the `powerflow` package under `src/`, with absolute imports.
- **Service settings:** only `src/powerflow/settings.py` (pydantic-settings; `DATABASE_URL`, `SITE_CONFIG_DIR`, `ACTIVE_SITE`, `LOG_LEVEL`).
- **Configuration:** sites (`SiteConfig`, `extra="forbid"`), their Modbus maps and the active site live in Postgres, behind `storage.ConfigRepository`.
  - Production uses `PostgresConfigRepository`; unit tests use `InMemoryConfigRepository`. `tests/repository_contract.py` runs against both.
  - Profile scenarios are still CSV files, in `storage.ProfileStore`.
  - `site_config/` holds only seed defaults (`storage.defaults`) plus the profile CSVs; the API never writes the seed files.
  - Validation happens before any write, in `core.SiteLibrary`.
  - Schema changes are new SQL files in `src/powerflow/storage/migrations/` (applied in order at startup). Never edit an applied migration.
- Pydantic models for every request/response; every route declares `response_model`.
- Point names (`<asset_type>.<asset_id>.<point>`) are the shared vocabulary. A measurement point's name is the field name on the snapshot model, so add both together; `test_points.py` checks that every point resolves.
- Every feature or fix ships with tests, and `make lint typecheck` stays clean.

## Gotchas
- **Grid impedance:** in pandapower, `ext_grid`'s `s_sc_max_mva`/`rx_max` only affect short-circuit studies. The power flow sees the grid strength through an explicit impedance element (see `network/topology.py`).
- **Site losses:** transformers plus collector feeders. They exclude the grid equivalent and the POI line, which are on the utility side of the POI meter.
- **`step_id` is the sim tick:** a real-time overrun skips ticks, so ids can have gaps and the skipped time is integrated as one longer step.
- **Non-convergence** keeps the last good snapshot (`converged=false`) and doesn't advance SOC.
- **Uploaded profiles:** a scenario saved with PUT keeps each asset's configured `scale`/`loop`, and hot-reloads into active-site assets even while running.
- **Tests never write the repo's `site_config/`:** anything that writes uses the `site_config_copy` fixture (a tmp copy).
- **Container data** lives on volumes, not in git: `powerflow-postgres-data` for sites, maps and the active site, and `powerflow-profiles` for the profile CSVs. `make down-all` (and root `make down-all`) deletes them, which resets to the shipped defaults.
- **Host `make run` needs Postgres** on `DATABASE_URL` (default localhost:5436).
- **Two things named site_config:** the folder `services/powerflow/site_config/` (data) and the package `powerflow.site_config` (the schema). Different paths, so imports don't clash.
- **`seed` must be ≥ 0:** it's a numpy SeedSequence. Load noise is keyed on (seed, step).
