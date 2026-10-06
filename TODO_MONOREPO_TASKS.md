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
- **There's no CI.** The checks only run through each clone's pre-commit hook (`make hooks`)
  and `make check`. See "CI" below.

## Deferred

- **CI** (deferred 2026-09-23). Root path-filtered workflows that call the same
  `make -C services/<svc> …` targets (and `make check-boundaries`, `make contracts-check`), so
  there's no new logic to write. They replace the inert `services/backend-ot/.github/`.
- **Deploy cutover** (deferred 2026-09-23). Point ArgoCD `repoURL`/`path` at this repo and the
  service directories, move the CD image-tag bump here, and introduce per-service release tags.
  Deployment files stay out of scope until this is picked up (root CLAUDE.md).
  web-plusdas's nginx now proxies `/powerflow-api` to `POWERFLOW_UPSTREAM`, resolved at start: a
  deployment without powerflow must set a resolvable upstream (or make it optional with a
  `resolver` + variable upstream), or nginx won't start.

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

- **First new Python service (optimizer or powerflow; ports 8010 / 8020 reserved).** Scaffold it
  with the `new-service` skill, so it doubles as the convention's real test. A Python consumer
  of backend-ot's contract will need a typed-client generator, which needs the user's OK on a
  dependency. See the typed-client rule in `contracts/README.md`.
