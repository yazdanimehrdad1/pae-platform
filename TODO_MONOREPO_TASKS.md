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

## Hardening

- **backend-ot:** move to a `src/pae_backend_ot/` package (removing the flat top-level module
  names), make mypy blocking or switch to pyright, and move black → `ruff format`.
- **mock-modbus:** add a type checker (`make typecheck` is a placeholder today).
- **web-plusdas:** run nginx as non-root (e.g. `nginxinc/nginx-unprivileged` listening on 8080).

## Next service

- **First new Python service (optimizer or powerflow; ports 8010 / 8020 reserved).** Scaffold it
  with the `new-service` skill, so it doubles as the convention's real test. A Python consumer
  of backend-ot's contract will need a typed-client generator, which needs the user's OK on a
  dependency. See the typed-client rule in `contracts/README.md`.
