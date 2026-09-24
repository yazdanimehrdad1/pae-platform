# PAE Platform — Monorepo Roadmap

> Living document. The single source of truth for the monorepo setup process.
> Every status change, decision, deviation from plan, or new item is recorded here
> (see **Decision & change log** at the bottom) and staged together with the phase it belongs to.


## Context
The two services were copied in verbatim. The audit showed that their code is fine, but everything around it still assumes one repo per service:
- a hand-made external Docker network (`pae-shared-network`) that the two Makefiles disagree on;
- `.env` loading that depends on the current directory, plus a `load_dotenv()` walk-up in `services/backend-ot/src/helpers/modbus/errors.py:13`;
- fixed `container_name`s and host ports;
- four different ruff versions, and pip in some places vs a `uv.lock` in others;
- a git hook that no longer resolves;
- agent config (`.claude/settings.json`, CLAUDE.md) that only exists per service.

**Objectives.** All four are first-class; a phase isn't done until it contributes to each one that applies to it.
1. **Services.** Every service runs standalone *or* together with the others, several at once, including from parallel agent worktrees.
2. **Contracts.** `contracts/` is the only shared surface between services. Specs are generated and checked for drift.
3. **Skills.** Every repeatable workflow in this repo is captured as a skill, so agents follow the same steps a human would: run the stack, add an endpoint, add a migration, add a mock device, change a contract, scaffold a service. A skill ships **in the same phase as the workflow it encodes**, not in a batch at the end, so it's written against commands that were just verified.
4. **Agents.** One consistent rule set (root + service CLAUDE.md, root `settings.json`) plus subagents that keep noisy work (test runs, boundary reviews) out of the main context.

**Out of scope (decided 2026-09-23):** CI/CD, k8s, ArgoCD. `services/backend-ot/.github/`, `k8s/`, `scripts/gcp_bootstrap.sh` and `docs/DEPLOYMENT.md` are left untouched and are marked inert or out of scope in the root CLAUDE.md.

**Decisions taken:**
- Move both services to uv, each with its own `pyproject.toml` + `uv.lock` (not a uv workspace).
- Makefile is the only entry point, with a POSIX shell on Windows too; `make.ps1` is removed.
- mock-modbus gets a real pytest suite.
- Local dev data starts fresh.
- `ZERO_MODE` stays `false`. backend-ot devices use `modbus_address_mode=one_based` (documented in `services/backend-ot/Readme-dev/service-readme.md:44-55`).

Nothing gets committed. I stage each phase, show you the diff, and wait for you before committing.

**Living roadmap file:** this file. Update it in the same change as the work it describes.

---

## The building blocks: what each one is, why it exists, and how it's used here

### 1. Service
- **What it is:** a directory under `services/<name>/` that is a complete, independent program: its own code, dependencies (`pyproject.toml` + `uv.lock`), Dockerfile, `compose.yaml`, Makefile, `.env.example` and CLAUDE.md.
- **Objective:** anyone (human, agent or CI) can build, test and run one service without knowing how the others work. A change to one service can't break another's build.
- **How it's used here:** today that's `backend-ot` (Modbus poller + historian API) and `mock-modbus` (a dev-only device simulator); `optimizer`, `powerflow` and `frontend` come later. Every service answers to the same command names (`make -C services/<svc> test`, `up`, `lint`…), so learning one teaches all of them.
- **Rule:** a service never imports another service's code or reads its files. Services talk over the network (HTTP, or Modbus for the mock), and share only `contracts/`.

### 2. Contract
- **What it is:** a machine-readable description of a service's public API. Here that's an **OpenAPI JSON file** at `contracts/openapi/<service>.openapi.json`, generated from the FastAPI app itself (`create_app().openapi()`), never hand-written.
- **Objective:** services depend on each other's *published interface*, not their source code. It's the one allowed shared dependency, so it's what keeps services decoupled yet compatible.
- **How it's used here:**
  - **Provider** (backend-ot): after changing an endpoint, run `make -C services/backend-ot contract`; the spec updates and the change shows up in the PR diff as a reviewable API change.
  - **Drift check:** each provider's unit tests fail while its committed spec is stale (so `make check` catches it), and `make contracts-check` regenerates every spec and fails if `contracts/` then differs from the git index. So a route can't change without the contract changing with it; the git hook runs it today, CI later.
  - **Consumers** (optimizer, frontend, later): generate a typed client from the spec, so a breaking change shows up as a compile or test error in the consumer rather than a runtime 422 in prod. The client generator is chosen when the first consumer exists (roadmap R1).
  - **Rules** in `contracts/README.md`: the provider owns its spec; a breaking change (removed or renamed field or route) needs a version bump and a note.
- **Not a contract:** mock-modbus's register maps. It speaks Modbus, not HTTP, and its maps are internal to its device files.

### 3. Rules for agents (CLAUDE.md, two levels)
- **What it is:** Markdown files that Claude loads automatically as instructions. The **root `CLAUDE.md`** loads in every session; a **service `CLAUDE.md`** loads when Claude works on files in that service.
- **Objective:** every agent, including subagents and parallel sessions, starts with the same facts and rules, without you repeating them. It's written once, applies everywhere, and is versioned with the code.
- **How it's used here:**
  - **Root** (about 80 lines): layout, the hard rules (no cross-service imports, contracts only, mock-modbus is dev-only, don't touch deploy files), the root make targets, the port registry, and the list of skills and agents.
  - **Service** (about 150 lines or less): what the service owns and doesn't own, its commands, the contracts it provides and consumes, and gotchas.
  - Long reference material (e.g. mock's register-authoring guide) moves *out* of CLAUDE.md into `docs/` or a skill, so it's only loaded when needed. That saves context on every other task.

### 4. Skill
- **What it is:** a folder with a `SKILL.md` holding a step-by-step procedure for one recurring task, plus optional templates. Its `description` tells Claude *when* to use it. Claude loads the body only when the task matches, so skills cost nothing until needed.
- **Objective:** repeatable workflows get done the same, correct way every time, by any agent: the right files touched, the right commands run, the right "done" check. Knowledge that today lives in your head or scattered READMEs becomes executable.
- **How it's used here:**
  - You say "add a voltage register to device 2" → Claude picks `mock-modbus:add-mock-device` → follows its steps (address band, file, test) → runs `make -C services/mock-modbus test` → done.
  - **Root skills** are for workflows that span services (`run-platform`, `contracts`, `new-service`). **Service-scoped skills** are for workflows inside one service (`add-migration`, `add-endpoint`, `add-mock-device`); they appear only when working there.
  - `new-service` is the key one for growth: it scaffolds optimizer, powerflow and so on to the convention, so new services start consistent.
- **Full inventory and phases:** see the tables in the Master roadmap below.

### 5. Subagent
- **What it is:** a specialised helper Claude can hand a task to, defined in `.claude/agents/<name>.md` with its own instructions, allowed tools and model. It works in its own context window and returns only a summary.
- **Objective:** keep noisy or narrow work out of the main conversation, so the main agent keeps a clean context, and let independent work run in parallel.
- **How it's used here:**
  - `test-runner` runs `make -C services/<svc> lint test [test-integration]` and reports only the failures. Hundreds of lines of pytest output never enter the main context.
  - `boundary-reviewer` is read-only. Before a commit it checks the diff for cross-service imports, an API change without a regenerated contract, mock-modbus leaking outside dev files, and secrets.
  - **In parallel:** e.g. one agent works on backend-ot in a git worktree while another works on the optimizer. Per-worktree test project names and configurable host ports (Phase 2a/3) are what make this safe.

### 6. Permissions (`.claude/settings.json`, root)
- **What it is:** the allow/deny list for what Claude may run or read in this repo.
- **Objective:** routine commands (`make`, `uv run`, `docker compose ps/logs`, read-only git) run without prompting you. Dangerous or private things are blocked outright: reading any `.env`, `docker volume rm`, `docker compose down -v`, `docker system prune`.
- **How it's used here:** there's one root file, so the rules apply no matter which service is being worked on. Always launch Claude from the repo root. The old per-service settings files are removed so they can't drift.

### 7. Guardrails (git hook + boundary check)
- **What it is:** `scripts/check_boundaries.py` (stdlib-only) plus a root `.githooks/pre-commit` (enabled with `make hooks`).
- **Objective:** enforce the monorepo rules mechanically, for humans and agents alike. CLAUDE.md *asks* for no cross-service imports; the hook *guarantees* it.
- **How it's used here:** on commit, the hook finds which services have staged changes, runs only their `lint`, runs the boundary check, and runs `contracts-check` if an API changed. CI (roadmap R3) later runs the same commands.

### 8. Dev stack (compose, two modes)
- **What it is:** each service's own `compose.yaml` (**standalone**), plus `deploy/compose/dev.yaml`, which `include`s them all (**together**).
- **Objective:** run one service, a few, or all of them, locally or in parallel worktrees, without editing files and without port or name collisions.
- **How it's used here:**
  - `make -C services/backend-ot up` is standalone: it reaches mock-modbus through `host.docker.internal`.
  - Root `make up` is together: one network, where services call each other by name (`mock-modbus:502`).
  - Host ports come from the port registry and can be overridden in the root `.env`, so both modes can run at once.
  - The `run-platform` skill drives all of this.

### How it fits together: one realistic task
You ask: *"Expose the latest reading timestamp on the devices endpoint so the optimizer can use it."*
1. Root CLAUDE.md tells the agent the rules. backend-ot's CLAUDE.md loads because the work is in that service.
2. The `backend-ot:add-endpoint` skill drives the change: model, router, integration test, then `make contract` regenerates `contracts/openapi/backend-ot.openapi.json`.
3. The `test-runner` subagent runs lint and tests and reports "all green" in a few lines.
4. The `contracts` skill classifies the spec diff as additive (non-breaking) and notes the consumers to update.
5. `run-platform` brings up the stack to confirm the endpoint live against mock-modbus.
6. `boundary-reviewer` checks the diff. The git hook re-runs lint, the boundary check and `contracts-check` on commit.
7. Later, the optimizer regenerates its client from the new spec; it never touches backend-ot's code.

---

## Master roadmap

**How each phase runs:** I implement → run its exit checks → stage → show you the diff and the check output → you commit → the next phase starts. Each phase leaves the repo working, so you can stop between any two.

| # | Phase | Status | Deliverable | Skill(s) shipped | Exit check (I run it) | Depends on |
|---|---|---|---|---|---|---|
| 1 | Repo hygiene | ✅ **Done** (`e7301b9`) | Root `.gitignore`/`.gitattributes`/`.editorconfig`, both `.dockerignore`s, lock file untracked | — | `git check-ignore` samples | — |
| 2a | backend-ot → uv + standard Makefile | ✅ **Done** (`f32712e`) | `uv.lock`-driven installs and Dockerfile; standard targets; `make.ps1` removed (its cloud targets move to `scripts/cloud.ps1`); anchored `env_file`; `load_dotenv` removed | `backend-ot:add-migration` | `make -C services/backend-ot install lint test test-integration build` pass; the skill adds a throwaway migration that applies in `test-integration`, then it's reverted | 1 |
| 2b | mock-modbus → uv + pytest suite | ✅ **Done** (`f32712e`) | New `pyproject` and `uv.lock`, uv Dockerfile, anchored `env_file`, real tests; device-authoring docs moved out of its 25 KB CLAUDE.md | `mock-modbus:add-mock-device` | `make -C services/mock-modbus install lint test build` pass; the skill adds a throwaway device that the new tests read, then it's reverted | 1 (can run in parallel with 2a) |
| 3 | Run standalone / together / concurrently | ✅ **Done** (`69ff983`, merged in `904e1d7`) | Per-service `compose.yaml`; `deploy/compose/dev.yaml`; root `Makefile` + `.env.example` | `run-platform` (root) | Standalone pair talks via `host.docker.internal`; root `make up` works by service name; both at once with no port clash; the built-in `run` skill picks up `run-platform` | 2a, 2b |
| 4 | Contracts | 🟡 **Staged, awaiting commit** (mock-modbus register map done early in Phase 3) | `export_openapi.py`, `contracts/openapi/backend-ot.openapi.json`, `contracts/README.md`, `make contract` / `contracts-check` | `contracts` (root), `backend-ot:add-endpoint` | Drift check is clean, and fails when a route changes; `add-endpoint` adds a throwaway route, its test and the regenerated spec, then it's reverted | 2a |
| 5 | Agent layer | | Root CLAUDE.md (lists every skill), root `.claude/settings.json`, 2 subagents, `check_boundaries.py`, root git hook; service CLAUDE.md files slimmed and pointing to their skills | `new-service` (root; needs every convention settled) | Launched from the root, every skill and agent is listed and scoped correctly; `new-service` scaffolds a dummy `services/_probe` that passes `make -C services/_probe lint test` and the boundary check, then it's deleted; `.env` read denied; a planted cross-import is blocked | 3, 4 |
| 6 | Stale docs | | READMEs and RUNBOOK local-dev sections updated | Skills audited: every command they quote matches the final Makefiles | Every command quoted in a doc or skill has been run once | 5 |

**Skill conventions (apply to all six skills):**
- **Location decides scope.** Repo-wide workflows go in `.claude/skills/<name>/SKILL.md`. Workflows that belong to one service go in `services/<svc>/.claude/skills/<name>/SKILL.md`, a directory-scoped skill that loads only when working in that service.
- **The frontmatter `description`** says *when* to use it (trigger phrases), not just what it does. That's what makes agents pick it.
- **The body** is a numbered procedure: which files to touch, the exact `make` targets to run, and a "done when" check. It points to existing docs rather than copying them, so there's one source of truth.
- **Templates and snippets** (e.g. `new-service/templates/`) live next to the `SKILL.md`.
- **Each skill is tested once, in a fresh session,** by asking for the task in plain words and confirming the skill is picked and the result passes its "done when". The `skill-creator` skill is available if you want formal evals later.
- **New services** get their service-scoped skills through `new-service`, so the skill set grows with the repo.

**Skill inventory at the end of this plan:**

| Skill | Scope | Encodes | Phase |
|---|---|---|---|
| `add-migration` | backend-ot | new `NNN_*.sql`, applied by `migrate_db.py`, proven in `test-integration` | 2a |
| `add-mock-device` | mock-modbus | new `device_N.py`, address bands, 32-bit registers, profile registers, test | 2b |
| `run-platform` | root | whole stack or one service, health checks, seed, logs, teardown, port overrides | 3 |
| `contracts` | root | regenerate spec, drift check, breaking-change rules, consumer follow-up | 4 |
| `add-endpoint` | backend-ot | router + pydantic models + integration test + `make contract` | 4 |
| `new-service` | root | scaffold to the convention and register it everywhere (root Makefile, dev compose, ports, CLAUDE.md) | 5 |

**Suggested order:** 2a → 2b → 3 → 4 → 5 → 6, with a commit after each.
- 2a comes first because it's the biggest risk (uv plus a Dockerfile change).
- 4 can move ahead of 3 if you'd rather have contracts sooner.

**After this plan: the roadmap, not yet planned in detail.**
- **R1: First new service (optimizer or powerflow).** Scaffolded with the `new-service` skill, so it doubles as the convention's real test. This is where the contract-client question gets decided (generator tool and where clients live); that needs your OK on a dependency.
- **R2: Frontend.** Same convention with a Node toolchain. The `new-service` templates gain a Node variant. The frontend consumes `contracts/openapi/*`.
- **R3: CI** (deferred, decided 2026-09-23). Root path-filtered workflows call the same `make -C services/<svc> …` targets, so there's no new logic to write. It replaces the inert `services/backend-ot/.github/`.
- **R4: Deploy cutover** (deferred, decided 2026-09-23). ArgoCD `repoURL`/`path`, the CD tag bump, and per-service release tags. Audit items 1.2 and 1.7 hold the checklist.
- **R5: Hardening.** Move backend-ot to a `src/pae_backend_ot/` package (removing the flat top-level module names), make mypy blocking or switch to pyright, and move black → `ruff format`.

---

## Target layout
```
pae-platform/
├── CLAUDE.md                      # monorepo rules + pointers (short)
├── Makefile                       # delegates to services; runs the dev stack
├── .env.example                   # host-port overrides ONLY (compose interpolation)
├── .gitignore  .gitattributes  .editorconfig
├── .githooks/pre-commit           # per-changed-service lint + boundary check
├── .claude/
│   ├── settings.json              # authoritative permissions (deny .env reads etc.)
│   ├── skills/{run-platform,new-service,contracts}/SKILL.md
│   └── agents/{boundary-reviewer,test-runner}.md
├── contracts/
│   ├── README.md                  # ownership + change rules
│   └── openapi/backend-ot.openapi.json   # generated, never hand-edited
├── deploy/compose/
│   ├── dev.yaml                   # include: every service → one network
│   └── backend-ot.dev.override.yaml
├── scripts/check_boundaries.py    # stdlib only: no cross-service imports/paths
└── services/<svc>/
    ├── CLAUDE.md  Makefile  compose.yaml  .env.example  .dockerignore
    ├── pyproject.toml  uv.lock  .python-version
    └── .claude/skills/<svc-specific>/SKILL.md
```

## The service convention (what every current and future service must provide)
- **Makefile targets, same names everywhere:**
  - `install` (`uv sync`), `lint`, `format`, `typecheck`, `test` (fast, no Docker where possible);
  - `test-integration` (if the service has one), `build`, `up`, `down`, `logs`, `run` (on the host), `contract` (services that publish to `contracts/`);
  - service-specific extras, e.g. `migrate` and `seed-db`.
- **`compose.yaml`** (renamed from `docker-compose.yaml`):
  - `name: <svc>`, no `container_name`, no external networks;
  - host ports as `${<SVC>_<THING>_PORT:-default}`;
  - `env_file: [{path: .env, required: false}]`;
  - container-network values (hostnames, internal ports) always go in `environment:`, which beats `env_file`.
- **Build context:** always the service directory, with a committed `.dockerignore`. When a service later needs `contracts/`, it gets it through a BuildKit named context; it never builds from the repo root.
- **Config:** pydantic-settings with `env_file` anchored to the service root via `Path(__file__)`. There's no walk-up `load_dotenv`, and nothing reads a root `.env`.
- **CLAUDE.md sections:** Owns / Does not own · Commands (the standard targets) · Contracts provided/consumed · Gotchas. Keep it to about 150 lines or less; deep reference material moves to `docs/` or a service skill.
- **Port registry** (in the root CLAUDE.md and `.env.example`):

  | Service | Port(s) |
  |---|---|
  | backend-ot | 8000 (http), 5435 (pg), 6380 (redis) |
  | mock-modbus | 502 |
  | optimizer (reserved) | 8010 |
  | powerflow (reserved) | 8020 |
  | frontend (reserved) | 5173 |

---

## Phase 1: Repo hygiene — ✅ DONE (commit e7301b9)
As built, with one deviation from the plan: the `.claude/*` rules use a `**/` prefix, because a pattern containing a slash is anchored to the repo root. The steps below are kept as a record.
1. Root `.gitignore` with the generic rules from both service `.gitignore`s. That covers Python caches, venvs, IDE and OS files, `.env`, `.env.local`, `.env.*.local`, `CLAUDE.local.md`, `.claude/settings.local.json`, **`.claude/scheduled_tasks.lock`**, `.ruff_cache/`, `.pytest_cache/` and `*.egg-info/`. Don't add a bare `lib/` or `build/`.
2. Trim the service `.gitignore` files:
   - `services/backend-ot/.gitignore` keeps only `/secrets`, `*.secret.yaml`, `/data`, `gcloud-notes.md`, `lib/`, `build/`, and **drops line 71 (`.dockerignore`)**;
   - `services/mock-modbus/.gitignore` is deleted.
3. `.gitattributes` with `* text=auto eol=lf`, `*.sh text eol=lf`, `Makefile text eol=lf`, and `*.ps1 text eol=crlf`. Then `git add --renormalize .`, and review that diff separately.
4. `.editorconfig` (LF, UTF-8, 4 spaces for py, tabs for Makefile).
5. `git rm --cached services/mock-modbus/.claude/scheduled_tasks.lock`.
6. Commit the existing `services/backend-ot/.dockerignore`. Add `services/mock-modbus/.dockerignore` modelled on it.
7. Delete the empty untracked directories under `services/mock-modbus/` (`.github`, `.githooks`, `docker`, `docs`, `scripts`, `k8s`). Later phases add `docs/`/`scripts/` back where needed.
8. Delete `stop_rm_all` (`services/backend-ot/Makefile:238-239`).

## Phase 2: uv + the standard Makefile, per service
**backend-ot**
- `pyproject.toml`:
  - add `pythonpath = ["src"]` to `[tool.pytest.ini_options]`;
  - raise the `pymodbus` floor to the version that introduced `device_id=` (I'll confirm it from the lock and changelog);
  - add a `.python-version` file set to `3.11`;
  - regenerate `uv.lock` with `uv lock`, never by hand.
- `docker/Dockerfile` builder:
  - `COPY --from=ghcr.io/astral-sh/uv:<pinned> /uv /bin/uv`, then `uv sync --frozen --no-dev --no-install-project`, copy `src/`, then `uv sync --frozen --no-dev`;
  - the runtime stage copies the venv as it does today;
  - pin `--uid 999`;
  - the path stays `docker/Dockerfile`, so the (inert) CI and deploy files aren't touched.
- `docker-compose.test.yaml` → `compose.test.yaml`:
  - `tests` uses the `ghcr.io/astral-sh/uv:python3.11-bookworm-slim` image with `UV_PROJECT_ENVIRONMENT=/opt/venv`, so the host `.venv` is never overwritten;
  - it caches through a named uv-cache volume and runs `uv sync --frozen && uv run python scripts/migrate_db.py && uv run pytest $PYTEST_TARGET`.
- `Makefile`, rewritten to the standard targets:
  - `SHELL` is a POSIX sh on Windows (Git's `sh.exe`; the first implementation step checks which shell make picks when started from PowerShell);
  - `lint` = `uv run ruff check src tests` (one ruff, from the lock);
  - `test` = `POSTGRES_PASSWORD=unit uv run pytest tests/unit`, on the host with no Docker;
  - `test-integration` uses the project name `backend-ot-test-$(WORKTREE_ID)`, where `WORKTREE_ID` comes from the repo-root directory name, so parallel agent worktrees don't collide;
  - `seed-db` uses `docker compose cp` instead of the container name;
  - `run` = `uv run python -m main` with `cd src`, which works once `env_file` is anchored;
  - `typecheck` = `uv run mypy src` (still non-blocking; switching to pyright isn't part of this plan).
- Delete `make.ps1`. Its `cloud-down`/`cloud-up` bodies move unchanged to `services/backend-ot/scripts/cloud.ps1`; that's deploy tooling, preserved as-is. The Makefile's Windows branch calls that script.
- `src/config.py:15`: `env_file = Path(__file__).resolve().parents[1] / ".env"`.
- `src/helpers/modbus/errors.py:7-18`: remove `load_dotenv()` and the `os.getenv` constants, and use `settings.modbus_host/port`. Drop `python-dotenv` from the dependencies only if nothing else imports it (checked with grep during implementation).
- `.githooks/` is removed; it's replaced by the root hook in Phase 5.

**mock-modbus**
- New `pyproject.toml`:
  - runtime dependencies are the current three from `requirements.txt`, unchanged;
  - dev dependencies are `pytest` and `ruff` (this is the approved addition);
  - `[tool.uv] package = false` keeps the `app/` layout and `python -m app.server` as they are;
  - ruff settings match backend-ot (line length 100, py311).
- Add `uv.lock` and `.python-version`, and delete `requirements.txt`.
- Dockerfile uses uv the same way; `WORKDIR` and `CMD` stay unchanged.
- `app/settings.py`: `env_file` anchored to the service root, plus `extra="ignore"`.
- `.env.example`: add the `PROFILE_*` keys.
- Tests:
  - the `tests/test_server.py` socket helpers move to `tests/modbus_frames.py`;
  - `tests/conftest.py` gets a fixture that starts `python -m app.server` as a subprocess on a free port with `RANDOM_SEED` set, waits for the port, and yields;
  - `tests/test_server.py` becomes real pytest tests, covering the current holding, input and unmapped cases plus one `profile_static` register;
  - `make test` = `uv run pytest`.
- The Makefile gets the standard targets. The `shared-network` bug and the `>nul` redirect disappear with Phase 3, and `clean` removes an `image: mock-modbus:dev` tag.

## Phase 3: Running standalone, together, and concurrently
- **Per-service `compose.yaml`**, following the convention above:
  - backend-ot: drop `pae-backend-ot-network`, `shared-network`, the three `container_name`s and the `./.env:/app/.env` mount. Ports become `${BACKEND_OT_HTTP_PORT:-8000}`, `${BACKEND_OT_POSTGRES_PORT:-5435}` and `${BACKEND_OT_REDIS_PORT:-6380}`.
  - backend-ot **standalone** default: `AGGREGATOR_MODBUS_HOST=host.docker.internal` plus `extra_hosts: ["host.docker.internal:host-gateway"]`. Then `make -C services/mock-modbus up` and `make -C services/backend-ot up` running side by side still talk to each other through the host port.
  - mock-modbus: `${MOCK_MODBUS_PORT:-502}:502`. This renames the ambiguous `MODBUS_PORT` interpolation; the in-container `MODBUS_PORT=502` stays.
- **Together:** `deploy/compose/dev.yaml`:
  ```yaml
  name: pae-dev
  include:
    - path: [../../services/backend-ot/compose.yaml, backend-ot.dev.override.yaml]
    - path: ../../services/mock-modbus/compose.yaml
  ```
  - The override sets `AGGREGATOR_MODBUS_HOST: mock-modbus` and `depends_on: mock-modbus`.
  - Every service shares the project's default network and addresses the others by service name.
  - Each included file keeps its own project directory, so build contexts, `env_file` and `.env` interpolation stay per service. I'll verify interpolation behaviour with `docker compose -f deploy/compose/dev.yaml config`.
  - mock-modbus appears only here and in its own directory, never in anything under `deploy/k8s`.
- **Concurrently:** the root dev stack and a standalone stack (or two worktrees) can run at the same time by overriding host ports in the root `.env`. The root `.env.example` lists every `*_PORT` variable and nothing else.
- **Root `Makefile`:**
  - `SERVICES := backend-ot mock-modbus`;
  - `up`, `down`, `logs`, `ps` run against `deploy/compose/dev.yaml`; `up svc=<name>` starts one service;
  - `install`, `lint`, `test` and `test-integration` loop `$(MAKE) -C services/$$s <target>`, and `<target> svc=<name>` narrows it to one service;
  - `check` = `lint` + `test` + `check-boundaries` + `contracts-check`;
  - `hooks` = `git config core.hooksPath .githooks`.

## Phase 4: Contracts
- `services/backend-ot/scripts/export_openapi.py` uses the stdlib plus the app itself. It calls `create_app().openapi()` and writes `contracts/openapi/backend-ot.openapi.json` with `sort_keys=True, indent=2`.
  - Its output path comes from a CLI argument that the Makefile passes. The service doesn't hardcode repo layout.
  - It runs with a dummy `POSTGRES_PASSWORD`, which is safe because `create_app` doesn't connect at import (confirmed in the lifespan code during implementation).
- `make -C services/backend-ot contract` regenerates it. Root `make contract` regenerates every provider, and `make contracts-check` regenerates and then runs `git diff --exit-code contracts/` (as built: also fails on untracked files, ignores the hand-written `*.md`).
- `contracts/README.md` covers:
  - the provider service owns its spec;
  - specs are generated, never edited by hand;
  - a breaking change needs a version bump and a note;
  - consumers never import provider code.

  Client generation (tool and output location) is decided when the first consumer (optimizer or frontend) arrives, because it adds a dependency.
- ~~mock-modbus exposes no HTTP API, so it has nothing to publish in `contracts/`.~~ Superseded 2026-09-24: it publishes its register map (see log).

## Phase 5: The agent layer
- **Root `CLAUDE.md`** (about 80 lines):
  - what the repo is and its layout;
  - hard rules: no cross-service imports or paths; `contracts/` is the only shared surface; each service is independently buildable; mock-modbus is dev-only; don't edit `.github/`, `k8s/` or the deploy scripts unless asked;
  - "work inside one service, and read its CLAUDE.md first";
  - the root and standard make targets;
  - the port registry;
  - the contracts workflow;
  - which skills and agents exist.
- **Service CLAUDE.md updates:**
  - backend-ot: rewrite "This repo diverges…" (`CLAUDE.md:9-16`) for uv; replace the `make.ps1` commands; fix the Gotchas port note; replace the "sibling repository" text in `Readme-dev/service-readme.md:19-25`.
  - mock-modbus: 25 KB is too big to load every time mock files are touched. Keep the overview, run instructions, config, conventions and gotchas. Move "How to add a device", address bands, 32-bit registers, timeseries and profiling into `docs/` and the `add-mock-device` skill. Delete the "Known issue" section.
- **`.claude/settings.json` (root, authoritative):**
  - allow `make:*`, `uv run:*`, `uv sync:*`, `docker compose ps/logs/config:*`, and read-only git;
  - deny `Read(**/.env)`, `Read(**/.env.local)`, `Read(**/.env.*.local)` (this pattern leaves `.env.example` readable), `docker volume rm`, `docker compose down -v` and `docker system prune`;
  - delete the service-level `settings.json` files, so the rule is "launch Claude from the repo root" and the settings can't drift. `settings.local.json` stays untouched.
- **Skills:** each one ships in the phase shown in the Skill inventory table. Only `new-service` is built in Phase 5; the rest are described here for reference.
  - `services/backend-ot/.claude/skills/add-migration` (Phase 2a): add `src/db/migrations/NNN_*.sql` following the numbering and the squashed baseline noted in backend-ot's CLAUDE.md "What this service owns", then prove it with `make test-integration`.
  - `.claude/skills/run-platform`: bring up the whole stack or one service, wait for health (`/api/healthz`, `/api/readyz`, and backend-ot's Modbus health route in `src/api/routers/health.py`), seed, show logs, and tear down. The built-in `run` skill picks it up.
  - `.claude/skills/new-service`: scaffold a service to the convention, using templates in `templates/` (Makefile, `compose.yaml`, Dockerfile, `pyproject`, `.env.example`, `.dockerignore`, CLAUDE.md). It then registers the service in the root `SERVICES`, `deploy/compose/dev.yaml`, the port registry and the root CLAUDE.md.
  - `.claude/skills/contracts`: when an API changes, regenerate the spec, run the drift check, spot breaking changes, and update consumers.
  - `services/backend-ot/.claude/skills/add-endpoint`: router + pydantic models + integration test + `make openapi`, following the existing conventions in its CLAUDE.md.
  - `services/mock-modbus/.claude/skills/add-mock-device`: content moved out of its CLAUDE.md.
- **Subagents (`.claude/agents/`):**
  - `boundary-reviewer` is read-only (Read/Grep/Glob plus `git diff`). It checks a diff for cross-service imports, API changes without a regenerated spec, mock-modbus leaking outside dev files, and secrets.
  - `test-runner` runs `make -C services/<svc> lint test [test-integration]` and returns only the failures, keeping noisy output out of the main context.
- **`scripts/check_boundaries.py`** (stdlib only): fails when
  - any `services/<a>/**/*.py` imports a module that exists only under `services/<b>`, or references `../<other-service>`;
  - any compose file, Dockerfile or pyproject in a service points outside its own directory, except `contracts/`.
- **`.githooks/pre-commit`:** works out which services have staged changes, runs `make -C services/<svc> lint` for each, then runs `check_boundaries.py`. It's enabled with `make hooks`.

## Phase 6: Stale documentation
- `services/backend-ot/README.md` (command sections), `docs/RUNBOOK.md` (local-dev sections only), and `services/mock-modbus/README.md` (Quick start): update to the uv and make commands and the new compose names.
- Deploy docs stay as they are.

---

## Verification
Before any command is quoted as working, I run it.

1. `make -C services/backend-ot install lint test`, then `make -C services/backend-ot test-integration`.
2. `make -C services/mock-modbus install lint test`, where the new pytest suite starts the server itself.
3. **Standalone and concurrent:**
   - start `make -C services/mock-modbus up` and `make -C services/backend-ot up`, then `make -C services/backend-ot seed-db`;
   - backend-ot's Modbus health route returns OK and readings appear.
   - This path goes through `host.docker.internal`.
4. **Together:**
   - `make down` in both services, then root `make up`;
   - `docker compose -f deploy/compose/dev.yaml ps` shows everything healthy;
   - repeat the health check and seed, with the connection going to `mock-modbus` by service name.
5. **Both at once:** root stack plus a standalone backend-ot with `BACKEND_OT_*_PORT` overridden. No conflicts.
6. **Parallel worktrees:** two git worktrees run `make test-integration` at the same time without clashing.
7. `make contracts-check` is clean. Changing a route makes it fail.
8. A planted cross-service import makes `make check-boundaries` fail, and the git hook blocks the commit. I then revert the planted import.
9. `git check-ignore -v` on sample paths (`.env`, `.claude/scheduled_tasks.lock`, a future `services/x/src/lib/`) behaves as intended.
10. Claude launched from the root: the skills and agents are listed, and reading a `.env` is denied.

Each phase ends with its diff staged and shown to you. Nothing is committed until you say so.

---

## Decision & change log

| Date | Phase | Entry |
|---|---|---|
| 2026-09-23 | 0 | Audit of the verbatim import completed (read-only). |
| 2026-09-23 | — | Scope: deployments (CI/CD, k8s, ArgoCD) out of scope for now; focus on services, contracts, skills, agents. |
| 2026-09-23 | — | Decisions: uv for all Python services (own pyproject + uv.lock each, no uv workspace); Makefile-only entry point with POSIX shell (make.ps1 removed); mock-modbus gets a real pytest suite; local dev data starts fresh; ZERO_MODE stays false (backend-ot devices use `one_based`). |
| 2026-09-23 | 1 | Done in `e7301b9`. Deviation: `.claude/*` ignore rules need a `**/` prefix because patterns containing a slash are anchored to the repo root. |
| 2026-09-23 | — | Skills made a first-class objective: each skill ships in the phase whose workflow it encodes. Building-blocks section added. Roadmap saved to `MONOREPO_ROADMAP.md`. |
| 2026-09-23 | 2a | Verified: make from PowerShell falls back to cmd.exe; service Makefiles set `SHELL` to Git's sh via 8.3 path (`C:/PROGRA~1/Git/bin/sh.exe`, override `GIT_SH=`) and export `MSYS_NO_PATHCONV=1` (Git-Bash otherwise rewrites `/app` → `C:/Program Files/Git/app`). Each service carries this snippet itself (no shared root include — services stay independent). |
| 2026-09-23 | 2a | pymodbus floor set to `>=3.10.0` — verified: 3.9.2 client uses `slave=`, 3.10.0 uses `device_id=`. |
| 2026-09-23 | 2a | `uv lock` refresh: lock was stale vs pyproject; removed leftover numpy/pandas/python-dateutil/six (nothing imports them). `python-dotenv` dropped as a direct dep (still present transitively via pydantic-settings). Dev deps moved to `[dependency-groups] dev`. |
| 2026-09-23 | 2a | uv container images are published on Debian **trixie**, not bookworm (`0.11.15-python3.11-trixie-slim`); matches `python:3.11-slim` (also trixie). |
| 2026-09-23 | 2a | Target semantics: `make test` = unit only (fast, host, no Docker); `test-all` = unit + integration (was `make test`). `test-unit` kept as alias. Integration project name is now `backend-ot-test-<worktree dir>`. |
| 2026-09-23 | 2a | Pulled forward from Phase 5/6: backend-ot CLAUDE.md "Python setup", "Commands" and lint sections, `tests/integration/README.md` commands — they described pip/make.ps1 and would mislead agents in the meantime. Rest of CLAUDE.md untouched until Phase 5. |
| 2026-09-23 | 2a | Exit checks run: `install`, `lint` (ruff 0.16.8), `test` (111 passed), `test-integration` (77 passed, stack torn down), `build`; image smoke: imports OK, uid/gid 999, pymodbus 3.15.0, no pytest/ruff shipped. `add-migration` skill probe: throwaway `005_*.sql` applied on top of baseline in `test-integration` (77 passed), then removed. **Not yet verified:** skill auto-discovery in a fresh Claude session (do at Phase 5 check). |
| 2026-09-23 | 2b | Repo is on OneDrive: uv's default hardlinks fail there (os error 396). Both services set `[tool.uv] link-mode = "copy"` in pyproject (applies to anyone syncing, no env var needed). backend-ot's pyproject change is staged with 2b. |
| 2026-09-23 | 2b | mock-modbus ruff: adopted backend-ot's rule set (E,W,F,I,B,C4,UP; ignore E501,B008) for consistency; 32 safe autofixes applied (Optional→`X \| None`, `timezone.utc`→`UTC`, import order, whitespace). `DeviceType(str, Enum)` kept with scoped `noqa: UP042` — StrEnum would change `str()`/format output. |
| 2026-09-23 | 2b | mock-modbus `.env` is now actually loaded (anchored `env_file`, `extra="ignore"`); previously only 3 compose-interpolated vars ever reached the process. |
| 2026-09-23 | 2b | Test suite (181 tests, ~1 s, no Docker): e2e reads of every declared register over raw Modbus TCP against a real server subprocess (expectations derived from the device files), device-file convention checks (bands, explicit `type=`, blocks build), datastore unit tests with a pinned clock. Mutation check: server on `ZERO_MODE=true` vs 1-based client → 67 failures, so the suite detects addressing errors. |
| 2026-09-23 | 2b | mock-modbus CLAUDE.md 24.7 KB → ~10 KB: device authoring → `docs/device-authoring.md`, profiles/timeseries → `docs/profiles-and-timeseries.md` (links rebased), "Known issue" removed (fixed). README quick start pulled forward from Phase 6 (it pointed at the deleted `requirements.txt`). |
| 2026-09-23 | 2b | Exit checks run: `install`, `lint`, `test` (181 passed), `up` (built, healthy, runs as `modbus`, reads over host port 502 for units 1–3), `down`. `add-mock-device` skill probe: a throwaway `device_4` written per the skill was auto-covered (191 passed); a 32-bit register whose low word leaves the band failed `test_device_maps`; probe removed. Skill auto-discovery in a fresh session still to verify at Phase 5. |
| 2026-09-23 | 3 (resolved 09-24) | **Found while writing the skill:** backend-ot's dev seed (`tests/seed_db/dev_mock_data.py`) defines one SEL-751 on unit 1 with 17 points at addresses 1400–1416 and no `modbus_address_mode` (defaults to `zero_based`). mock-modbus unit 1 serves keys 1–31 / 1001–1031. Run together, every seeded point reads the default value. Needs a decision before Phase 3's "readings appear" check. |
| 2026-09-24 | 3 | **Decision (user): backend-ot's dev seed must match and agree with mock-modbus; built from a contract, all 3 devices, all registers.** mock-modbus now publishes `contracts/modbus/mock-modbus.devices.json` (`app/contract.py`, `scripts/export_contract.py`, `make contract`; drift test `tests/test_contract.py`). backend-ot builds seed devices/points from it (`tests/seed_db/mock_modbus_seed.py`; strict parse models in `src/schemas/tests_models/mock_modbus_contract.py`): unit_id→server_address, `one_based`, file→poll_kind, width/sign/labels→data_type. The old hand-written SEL-751 seed device is gone. This pulls part of Phase 4 forward (first contract + `contracts/README.md`); the earlier "mock-modbus publishes nothing to contracts/" note is superseded. |
| 2026-09-24 | 3 | New standard target name `contract` = "regenerate what this service publishes to contracts/" (mock-modbus now; backend-ot's OpenAPI export will use the same name in Phase 4). |
| 2026-09-24 | 3 | Verified: seed builds 3 devices / 155 points (54+26+75; data types uint16, int16, uint32, enum16, bitfield16); 17 new backend-ot seed unit tests (mapping, one point per register, widths, no overlap via the app's own `validate_no_register_overlap`); backend-ot unit 128 passed, mock-modbus 183 passed. Drift mutation: renaming `pack_voltage` without `make contract` → "contract is stale" failure; reverted. |
| 2026-09-24 | 3 | **Not yet verified live** (seed → poll → readings): the old repo's dev stack (`pae_backend_ot`, from `…/pae-microservices-dev/pae_backend_ot`) is running and holds container names `pae-backend-ot*` and host ports 8000/5435/6380. Not stopped without the user's OK. Phase 3 removes fixed container names and makes ports overridable, which also lets both run side by side. |
| 2026-09-24 | 3 | Seeder matches points by name: renaming a mock register then re-seeding an existing dev DB leaves the old point at the same address. Documented in the `add-mock-device` skill. |
| 2026-09-24 | 3 | **Live-verified: seed agrees with mock-modbus.** With user OK, stopped the old repo's stack (`docker compose -p pae_backend_ot stop`; data kept). Ran both services over the current shared network, using a scratch-only compose override to reset the fixed `container_name`s (the stopped old containers still own those names; Phase 3 removes them in-repo). Seeded, let the scheduler poll: **3/3 devices, 155/155 points polled, 155/155 values inside their contract range.** Mock read log confirms exact alignment: every scan starts at the device's first register and ends at its last word (unit 1 holding 1–31 / input 1001–1031, unit 2 101–123 / 1101–1115, unit 3 201–299). Stacks torn down; old stack restarted as it was. |
| 2026-09-24 | 3 | Fixed pre-existing `seed-db` bug: `docker compose cp` can't create the missing parent `/app/tests` (tests aren't shipped in the image) — target now `mkdir -p` first. Seed is idempotent by name; the seed script logs nothing (no logging setup) — verify through the API. |
| 2026-09-24 | 2a–3 | Committed by user as `f32712e` (2a + 2b + contract-built seed). |
| 2026-09-24 | 3 | **Convention added:** compose *service and volume names are prefixed with the service directory name* (`backend-ot`, `backend-ot-postgres`, `backend-ot-redis`, `backend-ot-postgres-data`, `mock-modbus`). `include` merges every service's resources into one project, so unprefixed names (`postgres`, `redis`, `postgres-data`) would collide as soon as a second service brings a database. App service name == directory name, so `svc=<name>` works for the root fan-out and dev-stack targets alike. backend-ot's app service was renamed `pae-backend-ot` → `backend-ot`. |
| 2026-09-24 | 3 | `docker-compose.yaml` → `compose.yaml` in both services: `name:` set, no `container_name`, no custom/external networks (`pae-shared-network` gone), host ports `${BACKEND_OT_HTTP_PORT:-8000}` / `_POSTGRES_PORT:-5435` / `_REDIS_PORT:-6380` / `${MOCK_MODBUS_PORT:-502}`, optional `env_file: .env` (replaces the `./.env:/app/.env` mount), container-network values in `environment:`. Standalone backend-ot → `host.docker.internal` (+ `extra_hosts` host-gateway for Linux); overridable with `BACKEND_OT_AGGREGATOR_HOST/_PORT`. mock-modbus pins `ZERO_MODE=false` (the contract's 1-based numbering depends on it). |
| 2026-09-24 | 3 | Root dev stack `deploy/compose/dev.yaml` (`name: pae-dev`, `include:` both services; `backend-ot.dev.override.yaml` sets `AGGREGATOR_MODBUS_HOST=mock-modbus`). Verified with `docker compose config`: override merges into the included service, build contexts/env_file resolve per service, one default network, volumes `pae-dev_*`. Port overrides reach included files from both the shell and `--env-file`. |
| 2026-09-24 | 3 | Root `Makefile`: dev stack (`up [svc=]`, `down`, `restart`, `ps`, `logs`, `seed`, `e2e`) + fan-out (`install lint format typecheck test test-integration build contract`, skipped where a service lacks the target; unknown `svc=` fails) + `check` (= lint + test). Reads the root `.env` (ports only, `-include`) so `e2e` sees the same ports. Root `.env.example` = port registry + overrides only. |
| 2026-09-24 | 3 | `scripts/e2e/check_backend_reads_mock.py` (stdlib only, API + contract, no service imports) = `make e2e`. Replaces the scratch verify script. Fails with exit 1 when the API is unreachable or any point is missing/out of range. |
| 2026-09-24 | 3 | **Exit checks run:** `make check` (both services lint + test) from root; all 4 compose files `config -q`; **three stacks at once, 11 containers, no clash** — the old repo's stack on 8000/5435/6380, the standalone pair (mock on 502, backend-ot on 18000/15435/16380 via `host.docker.internal`) → AGREE 155/155, and the root dev stack (28000/25435/26380, mock 2502, by service name) → AGREE 155/155 with exact read alignment in the mock log. `make e2e` → AGREE. **Two worktrees ran `test-integration` concurrently** (`backend-ot-test-pae-platform` / `backend-ot-test-wt-probe`): 77 + 77 passed. All test stacks torn down; the old stack left running. |
| 2026-09-24 | 3 | ⚠ **OneDrive vs git worktrees:** removing the probe worktree failed (`Filename too long`, then `Permission denied`) — OneDrive had turned `.git/worktrees/wt-probe` into read-only cloud reparse points. Cleaned up manually. Parallel agent worktrees will hit this repeatedly while the repo lives under OneDrive; see open question in Phase 5. |
| 2026-09-24 | 3 | `run-platform` skill written (root `.claude/skills/`). backend-ot CLAUDE.md commands/gotchas, `Readme-dev/service-readme.md` wiring section and mock-modbus CLAUDE.md commands updated for the new compose layout. Untracked `CLAUDE.local.md` files (personal, not ours to edit) still mention `pae-shared-network`. |
| 2026-09-24 | — | **Repo moved out of OneDrive** (user decision): copied (robocopy, venvs/caches excluded) from `C:\Users\yazda\OneDrive\Desktop\pae-microservices-dev\pae-platform` to **`C:\dev\pae-platform`**, which is now the working copy. Verified: same HEAD `f32712e`, identical status and staged diff, `git fsck` clean, no reparse points in `.git`, personal ignored files (.env, CLAUDE.local.md, settings.local.json) carried over; `make install` + `make check` pass; `dev.yaml` validates; a git worktree was added, ran `test-integration` (77 passed) and removed cleanly — the failure OneDrive caused. The OneDrive copy is left untouched for the user to delete. Compose project names are fixed by `name:`, so Docker volumes/containers are unaffected. The `[tool.uv] link-mode = "copy"` setting (added for OneDrive) is kept: harmless and still needed by anyone syncing from a OneDrive folder. |
| 2026-09-24 | — | Minimal root `CLAUDE.md` added (points sessions at this roadmap + the hard rules) so a new Claude session at the new path starts with context; Phase 5 replaces it with the full rules. Observed: the root `run-platform` skill was auto-discovered by the running session — first evidence for the Phase 5 skill-discovery check. |
| 2026-09-24 | — | Merge `904e1d7` committed conflict markers into this file (log tail); resolved by keeping the HEAD side (the other side was empty). Phase 3 marked done: committed as `69ff983` (and the same content as `6042a44` on the remote), merged in `904e1d7`. |
| 2026-09-24 | 4 | backend-ot publishes `contracts/openapi/backend-ot.openapi.json` (OpenAPI 3.1, 36 paths, ~137 KB): `src/contract.py` (`render_openapi_contract`: `sort_keys`, indent 2, `ensure_ascii=False`, trailing LF), `scripts/export_openapi.py --output`, standard target `make contract` (roadmap said `openapi`; renamed to the `contract` convention set in Phase 3). Confirmed `create_app()` opens no connections: spec generated with `POSTGRES_HOST`/`REDIS_HOST` unresolvable; the Makefile passes the unit-test dummy `POSTGRES_PASSWORD`. |
| 2026-09-24 | 4 | Drift checked two ways: unit test `tests/unit/test_contract.py` (same pattern as mock-modbus, so `make check` catches drift), and root `make contracts-check` (regenerate all, then `git diff --exit-code` vs the **index** + no untracked files; hand-written `contracts/**/*.md` excluded). `contracts-check` is part of `make check` (user decision, next entry). Contract version for backend-ot = `info.version` (`create_app(version=...)`); for mock-modbus `CONTRACT_VERSION`. Dropped a planned "every route is published" test: FastAPI now nests `_IncludedRouter` objects in `app.routes`, and the check only re-derived `app.openapi()`. |
| 2026-09-24 | 4 | **Exit checks run:** backend-ot `lint` clean, `test` 130 passed. `contracts-check`: clean → pass; spec untracked → fail; stray untracked `.json` → fail; untracked `.md` → pass; route summary changed without regenerating → fail (and the unit drift test fails); reverted → pass. Mutation (renamed route path + query description) → both checks fail; reverted. `add-endpoint` skill probe: throwaway `GET /api/probe/site-count` (new router mounted in `create_app`, response model in `api_models`, integration test) → `make test` failed "contract is stale" until `make contract` (37 paths), then `lint`, `test` (130) and `test-integration` (78 passed) passed; `contracts-check` failed there, but on my unstaged edit to the hand-written `contracts/README.md` — which is why `*.md` is now excluded (re-verified above); probe fully reverted, spec back to 36 paths. Skills `contracts` (root) and `backend-ot:add-endpoint` written; `contracts/README.md` extended (targets, both drift tests, what counts as breaking, where each version lives); backend-ot CLAUDE.md points at both. |
| 2026-09-24 | 4 | **Decision (user): `make check` = `lint` + `test` + `contracts-check`** (option B, over keeping it separate for the pre-commit hook). One command covers everything; cost: `make check` fails mid-change until regenerated contracts are staged. Documented in the root Makefile help, `contracts/README.md` and the `contracts` skill. |
