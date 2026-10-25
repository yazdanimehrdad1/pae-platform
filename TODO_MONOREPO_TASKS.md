# Monorepo TODO

Open work on the monorepo itself (tooling, quality, infrastructure). It is not a feature
backlog. Remove an item when it's done; the commit that closes it records the details.

## Known debt (doesn't block feature work)

- **backend-ot's mypy reports 207 errors.** `make typecheck` is non-blocking by design
  (`mypy src || echo ...`). Fix them as part of hardening (below), then make it blocking.
- **web-plusdas still has loose TypeScript settings** (`strict: false`, `noImplicitAny: false`
  in `tsconfig.json` / `tsconfig.app.json`) **and 13 lint warnings** (`react-refresh/only-export-components`,
  two `react-hooks/exhaustive-deps` in `HistorianPage.tsx`). Turn on `strict` and fix what it
  finds, then clear the warnings.
- **Auth, Health, the SLD page and Notes still run on mock data** in web-plusdas.
  `services/web-plusdas/docs/backend-gaps.md` lists what backend-ot needs to add for each. It's
  backend-ot work first (`add-endpoint` skill, `make contract`), then the UI (`make -C services/web-plusdas api-types`,
  `add-api-call` skill).
## Production deployment

- **CI, CD and production hosting** are planned in stages in `deploy/PLAN.md` (Stages 0, 1 and 2 are
  done). CI runs on every PR to main and every push to main
  (`.github/workflows/ci.yml`); locally, `make hooks` and `make check`.

## Mobile (mobile-plusdas)

The app is bare-bones on purpose (2026-10-06): it only lists sites. The Alarms, Reports and
Assistant tabs say "coming soon". The backend work comes first, then the app:
- **Alarms and push notifications.** Site alarm state in the app, and pushes on faults. backend-ot
  has `notify_mobile` on alarm rules but sends nothing; a push channel (e.g. Expo Push) and
  device registration are backend-ot work. A first version was built and removed on 2026-10-06.
- **Reports** (needs a backend-ot report API) and **Assistant** (the AI agent).
- **Auth and a public gateway before real operators use the app.** backend-ot has no auth and
  is cluster-internal. The app must not point at an internet-reachable server until both exist.
- **Release builds over HTTP.** `preview`/production builds block cleartext. Serve backend-ot over
  HTTPS (comes with the gateway), or add a scoped cleartext exception for internal testing.

## Hardening

- **backend-ot:** move to a `src/pae_backend_ot/` package (removing the flat top-level module
  names), make mypy blocking or switch to pyright, and move black → `ruff format`.
- **mock-modbus:** add a type checker (`make typecheck` is a placeholder today).
- **web-plusdas:** run nginx as non-root (e.g. `nginxinc/nginx-unprivileged` listening on 8080).

## Point standard alignment

`services/powerflow/docs/point-standard/` (draft) defines standard Modbus point names, units,
signs and enums per asset class. powerflow's Modbus server serves it (the `powerflow_server`
column says which points); its HTTP point lists don't follow it yet. Align one service at a time,
provider first, with its contract regenerated (the gap table is in that folder's README.md):
- **powerflow:** make Modbus writable (setpoints over the protocol, through `PointRegistry.write`).
  Breakers, faults, comm loss and grid V/Hz events are injectable (Scenarios tab); frequency is
  still nominal plus a wander, not a dynamic model.
- **mock-modbus:** sign BESS power and current, add meter/relay/genset/met devices, and declare
  data_type and access in the contract.
- **backend-ot:** replace the placeholder STANDARDIZED templates with the tier-M points (lookup by
  `qty`), and map SLD roles to `qty`.

## Next service

- **intelli-gateway: engineer knowledge in Postgres.** Site data now comes from backend-ot
  (`services/backend_ot/`, strict models with a drift test against backend-ot's contract). With
  `USE_FAKE_DATA=false` the knowledge store (point guides, notes, manuals, IM scripts) is empty
  until its Postgres store and an authoring API exist.
- **backend-ot point classes in the powerflow seed.** `tests/seed_db/powerflow_seed.py` marks
  every bitfield as an ALARM point, so mode words like `DERMode` show up as active alarms
  (intelli-gateway's agent has to explain them away). Classify mode/status bitfields as BINARY.
