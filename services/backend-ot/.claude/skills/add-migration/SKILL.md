---
name: add-migration
description: Add or change a backend-ot database schema (new table, column, index, constraint, enum, data backfill) via a numbered raw-SQL migration. Use whenever a backend-ot change needs the Postgres schema to change, e.g. "add a column to devices", "new table for alarms", "index device_points_readings by X", "write a migration".
---

# Add a backend-ot database migration

backend-ot has no Alembic. Schema lives in numbered raw SQL files in
`src/db/migrations/NNN_<snake_case_description>.sql`, applied in filename order by
`scripts/migrate_db.py` and tracked in the `schema_migrations` table.

## Rules that are not obvious from the code

- **The version is the filename stem.** `migrate_db.py` records `NNN_description` in
  `schema_migrations`; renaming a file that has been applied anywhere makes it run again.
- **Never edit an applied migration.** There is no checksum. An edited file is silently
  skipped wherever it already ran, so dev, test and prod drift. Fix forward with a new file.
- **Each file runs inside one transaction.** Statements that can't run in a transaction
  (`CREATE INDEX CONCURRENTLY`, `ALTER TYPE ... ADD VALUE` on older PG) will fail. Use
  the non-concurrent form, or split the work and ask the user first.
- **Numbering:** next number = highest existing + 1, zero-padded to 3 digits. `001`–`004`
  are the squashed baseline (2026-09-22); don't reference the pre-squash tables listed in
  this service's CLAUDE.md ("What this service owns").
- **Plain Postgres.** Nothing calls `create_hypertable`; don't add TimescaleDB-only
  features unless the user asks.

## Procedure

1. `ls src/db/migrations/` and pick the next number.
2. Create `src/db/migrations/NNN_<description>.sql`. Copy the header style of the existing
   files:
   ```sql
   -- Migration: NNN_<description>
   -- <one line: why this change exists>
   ```
   Name constraints and indexes explicitly (`fk_<table>_<ref>`, `uq_<table>_<cols>`,
   `idx_<table>_<cols>`), and add `COMMENT ON` for new tables and columns, as the baseline does.
3. Keep the ORM in sync: update `src/schemas/db_models/orm_models.py`, the SQLAlchemy
   models that the app queries through.
4. If the change is visible through the API, update the pydantic request/response models
   in `src/schemas/api_models/` and the affected router or DB helpers. An API change also
   means regenerating the contract; use the `add-endpoint` skill for that part.
5. **A new table** must be added to `SERVICE_TABLES` in `tests/integration/conftest.py`.
   Otherwise its rows leak between integration tests.
6. Add or extend an integration test under `tests/integration/` that exercises the new
   schema through the API or DB helpers.

## Done when

- `make -C services/backend-ot lint` passes.
- `make -C services/backend-ot test` passes (unit tests).
- `make -C services/backend-ot test-integration` passes. That target builds a fresh
  Postgres, runs **all** migrations from zero via `scripts/migrate_db.py`, then runs the
  tests, which proves the new file applies cleanly on top of the baseline.
- For the running dev stack: `make -C services/backend-ot apply-migration` (the container
  entrypoint also applies pending migrations on start).
