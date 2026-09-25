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
contracts/           the ONLY shared surface: generated OpenAPI specs + mock register map
deploy/compose/      dev stack: includes every service's compose.yaml (`make up`)
scripts/             check_boundaries.py, e2e/ checks (stdlib only, no service imports)
.claude/             skills, agents (root); services add their own .claude/skills/
MONOREPO_ROADMAP.md  setup plan + decision log: record decisions/deviations there
```

## Hard rules
- **No cross-service code or files.** A service never imports another service's modules and never
  reads its files (no `../<other-service>`). Share data through `contracts/` and call over the
  network. `make check-boundaries` enforces this, and so does the pre-commit hook.
- **Contracts are generated, never hand-edited.** The provider regenerates them (`make contract`)
  in the same change as the code, and a breaking change needs a version bump and the user's OK.
- **Each service builds and tests on its own.** Its build context is its own directory, its
  config is its own `.env`, and nothing reads a root `.env` except the root dev-stack port overrides.
- **`services/web-plusdas` stays extractable** (`git subtree split --prefix=services/web-plusdas`).
  It depends only on `contracts/` and its own files, nothing outside it imports from it, and
  nothing is hoisted to the root: no root package.json, no npm/pnpm/yarn workspace, no Turbo/Nx.
  The root coordinates it only through the Makefile and `deploy/compose/`. The browser calls the
  API same-origin at `/api` (no CORS, no absolute URLs, no build-time env). See its CLAUDE.md.
- **`services/mock-modbus` is DEV-ONLY.** It is allowed only in its own directory, `deploy/compose/` and
  backend-ot's dev seed/tests. Never put it in a production manifest.
- **Deployment is out of scope** (CI/CD, k8s, ArgoCD). Don't edit `services/*/.github/`,
  `services/*/k8s/`, or backend-ot's `scripts/gcp_bootstrap.sh`, `scripts/cloud.ps1` and
  `docs/DEPLOYMENT.md` unless asked.
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
- **Dev stack (all services, one network), the default for development:** `make up [svc=]`,
  `down`, `ps`, `logs`, `seed`, `e2e`. See the `run-platform` skill. **The root takes priority:**
  `make up` resets, stopping every platform container (including services started on their own)
  before starting the dev stack, and `make down` stops them all (data volumes kept). `make down-all`
  is the destructive clean slate: it also deletes volumes (postgres/redis data), images and
  networks. To run one service alone, `make down` here first; a service's `up`/`build` refuses
  while the dev stack runs.

## Port registry (host ports; override in the root `.env`, see `.env.example`)
| Service | Port(s) |
|---|---|
| backend-ot | 8000 (http), 5435 (postgres), 6380 (redis) |
| mock-modbus | 502 |
| web-plusdas | 5173 (http; `make -C services/web-plusdas run` dev server: 5174) |
| optimizer (reserved) | 8010 |
| powerflow (reserved) | 8020 |

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
