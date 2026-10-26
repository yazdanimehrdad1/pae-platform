# pae-platform

Monorepo for the PAE platform: independent services that talk over the network and share
only machine-readable contracts. Launch Claude from this root. The repo's permissions and agents
live in the root `.claude/`.

```
services/<name>/     one self-contained service each (code, lockfile (uv.lock / package-lock.json),
                     Makefile, compose.yaml, Dockerfile, .env.example, CLAUDE.md, service-scoped skills)
  backend-ot/        Modbus poller + historian API (FastAPI, Postgres, Redis)
  mock-modbus/       DEV-ONLY Modbus TCP simulator standing in for the site devices
  web-plusdas/       the UI: Vite + React SPA served by nginx, /api proxied same-origin to backend-ot
                     /powerflow-api to powerflow (the Simulation page) and /intelli-gateway-api
                     to intelli-gateway (the PV forecast in the Historian)
  powerflow/         microgrid power flow simulator (pandapower) for EMS development: setpoints in,
                     measurements out; sites in its own Postgres (the only store), via the API
  mobile-plusdas/    Expo / React Native phone app (iOS + Android): bare-bones: lists backend-ot's
                     sites (alarms, push, reports, AI later); not containerized
  intelli-gateway/   AI helper for site engineers: Claude answers questions about a site through
                     read-only tools (tool-use loop, MCP-ready tool layer); also the PV forecast
                     (replaceable weather source, Open-Meteo now), stored in its own Postgres
contracts/           the ONLY shared surface: generated OpenAPI specs + mock register map
deploy/compose/      dev stack: includes every service's compose.yaml (`make up`)
deploy/PLAN.md       staged production plan (one GCP VM + Docker Compose); deploy/cloud/ (stack,
                     config) and deploy/infra/gcp/ (gcloud bootstrap) are added stage by stage
scripts/             check_boundaries.py, e2e/ checks, ci/ (CI helpers) (stdlib only, no service imports)
.github/             root CI: workflows/ci.yml (+ reusable _service-ci.yml, _build-image.yml), dependabot.yml
.claude/             skills, agents (root); services add their own .claude/skills/
TODO_MONOREPO_TASKS.md  open monorepo work (debt, hardening, pointers into deploy/PLAN.md); remove items when done
```

## Environments
- **local**: the laptop. `make up` runs every service from source in Docker, with mock-modbus and
  powerflow sites. The repo calls this the **dev stack** (`deploy/compose/`); it is not the dev environment.
- **dev**: a cloud mirror of prod with non-client data (GCP `pae-development`, VM `pae-dev`; public for
  demos at http://136.115.89.60, no login yet, see `deploy/STATUS.md`). It gets
  every merge to `main` automatically.
- **prod**: the real system with real sites and clients (GCP `pae-platform-prod`, VM `pae-prod`). It
  gets the same commit as dev, only after the owner approves.
- Cloud targets always name the environment: `make <target> env=dev|prod` (see `deploy/PLAN.md`).

## Hard rules
- **No cross-service code or files.** A service never imports another service's modules and never
  reads its files (no `../<other-service>`). Share data through `contracts/` and call over the
  network. `make check-boundaries` enforces this, and so does the pre-commit hook.
- **Contracts are generated, never hand-edited.** The provider regenerates them (`make contract`)
  in the same change as the code, and a breaking change needs a version bump and the user's OK.
- **Each service builds and tests on its own.** Its build context is its own directory, its
  config is its own `.env` locally (in the dev and prod clouds: `deploy/cloud/config/<env>.env` plus
  its secrets from GCP Secret Manager, written by `deploy/cloud/scripts/deploy.sh`), and nothing reads a root `.env` except the root dev-stack
  port overrides.
- **`services/web-plusdas` stays extractable** (`git subtree split --prefix=services/web-plusdas`).
  It depends only on `contracts/` and its own files, nothing outside it imports from it, and
  nothing is hoisted to the root: no root package.json, no npm/pnpm/yarn workspace, no Turbo/Nx.
  The root coordinates it only through the Makefile, `deploy/compose/`, `deploy/cloud/` and root
  `.github/` (its image is built from its own directory). The browser calls the
  APIs same-origin: `/api` (backend-ot), `/powerflow-api` (powerflow) and `/intelli-gateway-api`
  (intelli-gateway), the last two forwarded to their `/api` (no CORS, no absolute URLs, no
  build-time env). See its CLAUDE.md.
- **`services/mock-modbus` is DEV-ONLY.** It is allowed only in its own directory, `deploy/compose/`,
  backend-ot's dev seed/tests and root CI tests. Never put it in a production manifest:
  `deploy/cloud/`, `deploy/infra/`, `deploy/k8s/` or the root deploy/build workflows.
- **Production deployment** lives in `deploy/cloud/`, `deploy/infra/` and root `.github/`; the staged plan is
  `deploy/PLAN.md`. Work on it one approved stage at a time. These files coordinate services only
  through published images, env and `make -C`, never through paths into a service directory (no
  `include`/`extends` of `services/*/compose.yaml`, no `../services/...`). Never read or print
  a secret value (Secret Manager versions, `/opt/pae/secrets/` on the VM). Scripts may generate
  random passwords straight into Secret Manager; the user adds API keys.
- Never read or edit `.env` files (only `.env.example`). Never delete Docker volumes
  (`down -v`, `volume rm`, `make down-all`) unless the user asks for it in this conversation.

## Working in a service
Work inside one service at a time, and read `services/<svc>/CLAUDE.md` first. It says what the
service owns, lists its commands, contracts and gotchas, and names its skills. A change that
spans services is done one service at a time: the provider and its contract first, then each consumer.

## Commands
Make is the only entry point (on Windows too, where recipes run in Git's sh). `make help` works at
the root, and `make -C services/<svc> help` in each service.
- **Standard targets in every service:** `install lint format typecheck test build up down logs
  run`, plus `test-integration` and `contract` where the service has them.
- **Root fan-out:** `make <target>` runs it in every service that has it. `svc=<name>` narrows it.
  web-plusdas's `test-integration` checks the running container, so it needs the dev stack up.
- **Root checks:** `make check` = lint + typecheck + test + `check-boundaries` + `contracts-check` (stage
  regenerated contracts first). `make hooks` enables the pre-commit hook once per clone.
- **CI** (`.github/workflows/ci.yml`) runs the same make targets: on a PR, the changed services
  (plus a changed contract's consumers, `scripts/ci/changed_services.py`), the root checks and a
  build + smoke test of changed production images; on `main`, everything, then pushes
  `us-central1-docker.pkg.dev/pae-platform-prod/pae/pae-<svc>:<git sha>` (Artifact Registry, through Workload Identity Federation) for the four deployed services. The one required check is
  "CI result". A new service or contract consumer goes into `scripts/ci/changed_services.py`.
  Third-party actions are pinned to commit SHAs (Dependabot updates them). `.github/workflows/deploy.yml`
  then deploys each green `main` commit to dev automatically, and to prod only with the owner's approval.
- **Dev stack (all services, one network), the default for development:** `make up [svc=]`,
  `down`, `ps`, `logs`, `seed-mock-modbus`, `seed-2bess-1pv`, `e2e`, `e2e-2bess-1pv`, and for the
  phone app `mobile-dev`. See the `run-platform` skill. **The root takes priority:**
  `make up` resets, stopping every platform container (including services started on their own)
  before starting the dev stack, and `make down` stops them all (data volumes kept). `make down-all`
  is the destructive clean slate: it also deletes volumes (postgres/redis data, including
  powerflow's stored sites and profile edits), images and networks. To run one
  service alone, `make down` here first; a service's `up`/`build` refuses while the dev stack
  runs.

## Port registry (host ports; override in the root `.env`, see `.env.example`)
| Service | Port(s) |
|---|---|
| backend-ot | 8000 (http), 5435 (postgres), 6380 (redis) |
| mock-modbus | 502 |
| web-plusdas | 5173 (http; `make -C services/web-plusdas run` dev server: 5174) |
| optimizer (reserved) | 8010 |
| powerflow | 8020 (http), 5436 (postgres), 1502 (modbus; 502 in the container) |
| mobile-plusdas | 8081 (Expo Metro dev server, `make -C services/mobile-plusdas run`; no container) |
| intelli-gateway | 8030 (http), 5437 (postgres) |

## Contracts
Rules and the contract list are in `contracts/README.md`. For a change that alters what a service
exposes: change the provider, run `make -C services/<svc> contract`, classify the diff
(additive or breaking), update consumers, and commit it all together. The `contracts` skill
holds the full procedure.

## Skills (they load when the task matches)
- Root: `run-platform` (run/seed/check the stack), `contracts` (change or check a contract),
  `new-service` (scaffold and register a Python API or Node frontend service).
- backend-ot: `add-endpoint`, `add-migration`. mock-modbus: `add-mock-device`. web-plusdas: `add-api-call`.

## Agents
- `test-runner` runs a service's lint and tests (or `make check`) and reports only the failures.
  Use it instead of reading full test output.
- `boundary-reviewer` is a read-only review of a diff against these rules (boundaries,
  contracts, dev-only, secrets). Run it before calling a change done.
