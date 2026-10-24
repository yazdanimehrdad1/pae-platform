# Production deployment: clean slate + master plan (rev. 2)

## Context
The only deployment work in the repo is backend-ot's old GKE + ArgoCD + Cloud SQL setup. It predates the monorepo:
- ArgoCD points at the old repo.
- The service-level `.github/` is inert, and `ci.yml` is broken.
- It covers one service only.
- It never solved how the cloud reaches site Modbus devices.

It gets removed, the useful lessons are kept, and production is rebuilt from scratch for backend-ot, intelli-gateway, powerflow and web-plusdas. mobile-plusdas is excluded, and mock-modbus stays dev only.

Constraints:
- 1 site to start, designed for multiple sites, few users.
- Only **dev** (local `make up`) and **prod**.
- Site links can be VPN, direct, through the RTAC aggregator, or backend-ot on site.
- Kubernetes/GKE must stay an easy later step.

Each stage starts only after the owner approves it. Cost figures are estimates from GCP list prices; check them in the GCP pricing calculator.

## Decisions (rev. 2)
| # | Decision |
|---|---|
| Platform | **Option A on GCP:** one VM, Docker Compose. e2-standard-2, us-central1, 20 GB boot disk, 50 GB pd-balanced data disk, static IP, daily snapshots, GCS backup bucket (restic). |
| Neutral stack | Unchanged: GHCR, sops + age, restic, Tailscale, Caddy, Grafana Cloud + Alloy |
| Database | **Plain PostgreSQL 16**, the same image in dev and prod. No TimescaleDB. |
| Historian | **No retention work**: readings are kept indefinitely in one plain table; storage is handled by growing the data disk. This plan covers deployment only. |
| Environments | dev (laptop) and prod only |

---

## Platform: why Option A (VM + Compose) over B (GKE + ArgoCD) now
| | **A. One GCE VM + Docker Compose (chosen)** | **B. GKE Autopilot + Cloud SQL + ArgoCD (later)** |
|---|---|---|
| Fit for 1 to about 10 sites, 4 services + 3 Postgres + Redis | Right-sized | Built for many services and teams |
| Reuses what exists | Yes (services already run as a compose stack) | New manifests for everything |
| Site VPN (Tailscale/WireGuard) | Runs on the VM, minutes per site | Autopilot blocks NET_ADMIN; Cloud VPN or the Tailscale operator needed |
| Single-instance pieces (poller leader, intelli-gateway conversations, SSE, powerflow engine) | Natural | Need sticky routing / `replicas: 1` |
| Same artifact on site (edge backend-ot) | Same compose file | k3s or a second method |
| Cost, 1 site | about $62/month (about $44 committed) | about $150–250/month |
| HA | Single VM; snapshots + backups, restore in under 1 h | Multi-zone, self-healing |

Cloud Run doesn't fit: backend-ot is a long-running poller, powerflow serves raw Modbus TCP, and VPN egress is awkward there.

---

## Cost (estimates from GCP list prices for us-central1, from memory; check every line in the GCP pricing calculator)

Separate usage-based costs, not in the tables: Claude API (intelli-gateway), Open-Meteo commercial key (PV forecast), domain name.

**Measured per-site data rate (2bess-1pv):**
- 9 devices, 415 logged points, 73k rows/hour, about 214 B/row including 4 indexes.
- That is about **11.4 GB/month per site**. Readings are kept indefinitely (no retention in this work), so storage grows by that much every month: about **137 GB after year 1**.
- The other 2 databases (intelli-gateway, powerflow) are under 1 GB.

**(a) Platform cost.** Fixed, shared by all sites.
| Item | Monthly |
|---|---|
| VM e2-standard-2 (2 vCPU, 8 GB): about $0.067/h × 730 h | $48.91 (1-year CUD: about $30.80) |
| Boot disk, 20 GB pd-balanced @ $0.10/GB | $2.00 |
| Static external IPv4, in use @ $0.005/h | $3.65 |
| Boot-disk snapshots (about 8 GB used @ $0.05/GB) | about $0.40 |
| Backup bucket, platform part (other 2 DBs, configs; under 2 GB @ $0.020/GB) | about $0.05 |
| Network egress (Tailscale traffic, monitoring push; mostly inside free/standard-tier allowances) | about $0–1 |
| Security, VPN, secrets, registry, monitoring: Tailscale free, sops/age, GHCR free, Grafana Cloud free tier | $0 |
| **Platform total** | **about $55** (**about $37** with a 1-year CUD) |

**(b) Database storage cost.** It grows with the data. Each stored GB costs about **$0.16/month** all-in:
- data disk $0.10 (pd-balanced, provisioned with headroom below the 80% alert)
- daily snapshots, 7 kept, about $0.05
- restic dumps in GCS, about $0.01

The data disk starts at 50 GB and is resized online when it reaches 80%. It can grow but never shrink.

| 1 site, month | Stored | Data disk | DB storage | **Total on-demand** | **Total committed** |
|---|---|---|---|---|---|
| 1 | about 11 GB | 50 GB | about $6 | **about $61** | **about $43** |
| 3 | about 34 GB | 50 GB | about $7 | **about $62** | **about $44** |
| 6 | about 68 GB | 100 GB | about $14 | **about $69** | **about $51** |
| 12 | about 137 GB | 200 GB | about $28 | **about $83** | **about $65** |
| 24 | about 274 GB | 350 GB | about $50 | **about $105** | **about $87** |

**How it scales per extra site:**
- Each extra 2bess-1pv-sized site adds about 11.4 GB/month, so **about +$1.80/month more storage cost every month** (about +$22/month after its first year).
- **VM upsize step:** e2-standard-4 (4 vCPU, 16 GB) adds about **$49/month** on-demand (about $31 committed). Expect it at about 5 sites, several simultaneous powerflow simulations, or a historian large enough that queries need more RAM. The trigger is CPU, memory or query latency measured in Grafana, not a site count.

| After 12 months | Stored | Data disk | DB storage | VM | Platform | **Total on-demand** | **Total committed** |
|---|---|---|---|---|---|---|---|
| 1 site | 137 GB | 200 GB | about $28 | e2-standard-2 | about $55 | **about $83** | **about $65** |
| 2 sites | 274 GB | 350 GB | about $50 | e2-standard-2 | about $55 | **about $105** | **about $87** |
| 5 sites | 685 GB | 900 GB | about $128 | e2-standard-4 | about $104 | **about $232** | **about $196** |

- **Storage scales with logged points × poll rate.** 1,000 points at a true 10 s is about 4.9× the 2bess-1pv rate.


---

## Stage 0 (first change): remove the old deployment and keep the lessons
Delete from `services/backend-ot/`:
- `.github/`
- `k8s/`
- `scripts/gcp_bootstrap.sh`, `scripts/cloud.ps1`
- `docs/DEPLOYMENT.md`, `docs/RUNBOOK.md`, `docs/PER-SERVICE-CHANGES.md`, `docs/prompt-Deployment-CI-CD.md`

Edit:
- `services/backend-ot/Makefile`: remove the cloud section `:208-259`, `.PHONY` `:28`, and help lines `:5`, `:73`.
- `services/backend-ot/Makefile`: keep `:13-22` (Git-sh setup, not cloud-only).
- `services/backend-ot/CLAUDE.md:19,148-149`; `README.md:7,11`; `tests/integration/api/routers/test_health.py:4`: reword the k8s mentions.
- `services/backend-ot/.dockerignore:42-47`: drop the `k8s/` and `.github/` lines; `docker-compose*` → `compose*`.
- Comment-only cleanup (k8s/GKE/ArgoCD wording):
  - `.env.example:5-6,34-35,57,91-95,101-104`
  - `docker/Dockerfile:43,64-65,72-74`
  - `docker/entrypoint.sh:42-46`
  - `src/config.py:63,91-92` (comments only; the code stays)
- `services/backend-ot/.gitignore:32` (`gcloud-notes.md`): keep until you delete that file.
- `services/mock-modbus/CLAUDE.md:4`: "never in a production manifest (k8s, overlays…)" → name `deploy/prod/`, `deploy/infra/`, `deploy/k8s/`, root `.github/` deploy workflows.
- **Keep:** `POD_NAME` and leader election (`src/config.py`, `src/scheduler/locks.py`), and the Dockerfile and entrypoint (dev uses them).
- **Leave:** the `/readyz` docstring in `src/api/routers/health.py` (avoids contract and client churn).
- **Root `CLAUDE.md`:**
  - `:44-48`: the "Deployment is out of scope" rule becomes "Production deployment lives in `deploy/prod/` + `deploy/infra/` (see `deploy/PLAN.md`). These coordinate services only through images, env and `make -C`, never through paths into a service directory (no `include`/`extends` of `services/*/compose.yaml`, no `../services/...`)."
  - "Its config is its own `.env`": add "in dev; in prod, `deploy/prod/config/<svc>.env` + `deploy/prod/secrets/<svc>.sops.env`".
  - web-plusdas rule: the root coordinates it through the Makefile, `deploy/compose/`, `deploy/prod/` and root `.github/`.
  - mock-modbus rule: forbidden in `deploy/prod/`, `deploy/infra/`, `deploy/k8s/` and the root deploy/build workflows.
- **`.claude/agents/boundary-reviewer.md`:**
  - `:33`: same update as the mock-modbus rule.
  - `:36`: allow committed sops-encrypted `*.sops.env` files; flag any secrets file without a `sops:` block or `ENC[` values.
  - `:38-40`: replace the out-of-scope list.
- **`scripts/check_boundaries.py`:**
  - Dev-only scan (`:17,199-204`): **keep its current scope, all of `deploy/` except `deploy/compose/`**, so the future `deploy/k8s/` is covered. Skip `*.md` (docs aren't manifests; `deploy/PLAN.md` mentions mock-modbus by name). Add the root `.github/workflows/deploy-prod.yml` and `_build-image.yml`, but **not** `ci.yml`, which legitimately tests mock-modbus.
  - Outside-in check: add `deploy/prod` and `deploy/infra` to `SHARED_DIRS` (`:39`), so a `../services/...` path there is caught.
  - New check, written in Stage 5 with the first sops file: every `deploy/prod/secrets/*.sops.env` is encrypted.
- **`TODO_MONOREPO_TASKS.md`:**
  - Replace "There's no CI" (`:18-19`), the CI item (`:22-25`) and "Deploy cutover" (`:26-28`) with a pointer to `deploy/PLAN.md`.
  - Keep `:29-31`, the nginx `POWERFLOW_UPSTREAM` lesson; Stage 1 uses it.

New:
- `deploy/PLAN.md`: this plan.
- Memory file `deploy-lessons-from-old-gke-setup.md` plus its MEMORY.md line. It records:
  - liveness has no dependencies; readiness checks DB and Redis
  - one poller via the Redis leader lock (TTL 30 s); one uvicorn process per container
  - migrations run once before the app; Redis is ephemeral
  - immutable SHA tags; never "revert the tag-bump commit"
  - the entrypoint CRLF fix, the import smoke test, and the dummy `POSTGRES_PASSWORD` in CI
  - Cloud SQL `--edition=ENTERPRISE` for custom tiers; the Windows `gke-gcloud-auth-plugin` PATH
  - ArgoCD: Sync hook + `BeforeHookCreation` for migrations, HPA/PDB in a late wave, the `includeSelectors` label trap

⚠ `services/backend-ot/Readme-dev/gcloud-notes.md` (untracked, gitignored) reportedly holds a plaintext Cloud SQL password for `prd-pae-rtac-server`. Don't open or share it: rotate or delete that instance, then delete the file.

---

## Stage 1: Deployment readiness in code (done 2026-10-24)
Only what the deployment needs. The service features listed under "Not in this work" below are left alone.

**Done:**
- **Postgres image:** all three services (backend-ot, intelli-gateway, powerflow) pin `postgres:16.15-alpine` in `compose.yaml` and `compose.test.yaml`; prod uses the same image. backend-ot moved off `timescale/timescaledb:latest-pg16` (an old dev volume created by the Timescale image won't start on plain Postgres: recreate it once and reseed). `/health` `timescaledb_version` now returns `null` (no contract change).
- **intelli-gateway `/api/readyz`:** 200 `{ok, database: "ok" | "not_configured"}`, 503 `database: "unavailable"` when its configured Postgres doesn't answer. Contract change, additive (new path + `ReadinessResponse`); web-plusdas `api-types` regenerated.
- **web-plusdas nginx:** `resolver ${NGINX_RESOLVER}` (default `127.0.0.11`, Docker's DNS; the cluster DNS on Kubernetes) and variable upstreams, with `rewrite` for the `/powerflow-api/` and `/intelli-gateway-api/` prefix swaps. nginx now starts while an upstream is down; that route answers 502 until it is back.

**Decided not to change (and why):**
- **Health checks the deploy waits on:**
  - backend-ot `/api/readyz` (DB + Redis), already exists
  - intelli-gateway `/api/readyz` (new)
  - powerflow `/api/health`: it migrates its DB at startup and fails to start without it, so a separate readiness route would be a contract change for nothing
  - web-plusdas `/`
- **Migrations:** backend-ot runs `scripts/migrate_db.py` as a one-shot `backend-ot-migrate` service in prod (`RUN_MIGRATIONS_ON_START=false`), because it can run several replicas. intelli-gateway and powerflow keep migrating at startup: each runs as a single replica by design (in-process conversations / simulation engine), and intelli-gateway already takes an advisory lock. Kubernetes keeps the same split.
- **backend-ot `reload=True` in `main.py`:** only `make run` on a laptop uses it; the image's `CMD` runs uvicorn without reload.
- **`src/schemas/tests_models/mock_modbus_contract.py`:** that folder is backend-ot's documented home for test-only models, and app code never imports it. It ships in the image as an unused file; it never runs.

### Not in this work (deployment only)
- **Historian retention, partitioning, downsampling, archiving:** none. Readings are kept indefinitely; storage is handled by growing the data disk (see Cost).
- **Per-site aggregator host:** backend-ot has one global `AGGREGATOR_MODBUS_HOST`, which serves one site's RTAC. That's enough for the first site. Multi-site support is a backend-ot feature for later (contract change; consumers intelli-gateway, web-plusdas, mobile-plusdas).
- **Poll interval:** the measured poll is about every 20 s against the configured 10 s; a backend-ot question, not a deployment one.
- **powerflow multi-user isolation:** one active site per process today.

---

## How the deploy files are laid out
```
deploy/
  compose/                 (existing) dev stack, builds from source, includes mock-modbus
  prod/
    compose.prod.yaml      image: ghcr.io/<you>/pae-<svc>:${RELEASE}, never build:; volumes on the data
                           disk, healthchecks, resource limits, *-migrate one-shot services. No mock-modbus.
                           Self-contained: never include/extends services/*/compose.yaml (backend-ot's
                           defaults its aggregator to the mock) and no ../services/... paths.
    Caddyfile              TLS + routing to web-plusdas (nginx keeps /api, /powerflow-api, /intelli-gateway-api)
    Makefile               prod-* targets (called from the root Makefile)
    config/                non-secret env per service, plain text, committed
    secrets/               <svc>.sops.env + host.sops.env, encrypted with sops+age, committed
    scripts/               deploy.sh, backup.sh, host-setup.sh
  infra/
    gcp/main.tf            OpenTofu (primary): VM + SA, boot + data disk, static IP, firewall,
                           snapshot schedule, backup bucket, state bucket
  k8s/                     (future) kustomize base + overlays/prod
  PLAN.md
.sops.yaml                 (repo root) age PUBLIC key + which files to encrypt
```
- One release = one git SHA for all services.
- The VM is reached by its Tailscale name `pae-prod`, so `deploy.sh` doesn't depend on the provider.

## CI/CD
```
 PR ──► CI: changed services' make lint/typecheck/test + check-boundaries + contracts-check (required checks)
 merge to main ──► CI: build + smoke-test all 4 images ──► push ghcr.io/...:<sha>
        ──► deploy-prod: waits for your Approve (GitHub Environment "production")
        ──► join Tailscale (tag:ci) ──► sops decrypt ──► deploy.sh <sha> on pae-prod:
             pre-deploy pg_dump ─► pull ─► *-migrate one-shots ─► up -d ─► health checks
             ─► OK: record RELEASE (keep RELEASE.prev) │ FAIL: auto-redeploy RELEASE.prev
```
- **Workflows:** `ci.yml`, reusable `_service-ci.yml` and `_build-image.yml`, `deploy-prod.yml` (also `workflow_dispatch` with any SHA, which is how you roll back).
- **Path filters include contract consumers:** a change to `contracts/openapi/backend-ot.openapi.json` also runs web-plusdas, mobile-plusdas and intelli-gateway; powerflow's and intelli-gateway's specs also run web-plusdas. PRs touching backend-ot also run its `make test-integration` (Postgres/Redis service containers).
- **The image build matrix is an explicit list** of the 4 prod services, not the root `Makefile` `SERVICES` list (`Makefile:26`, which includes mock-modbus). Each image is built from its own service directory as the context (web-plusdas: `services/web-plusdas` + `docker/Dockerfile`), which keeps `git subtree split` intact.
- **Standards:**
  - least-privilege `permissions:`; actions pinned to commit SHAs; Dependabot
  - no secrets on fork PRs; branch protection on `main`
  - concurrency groups, job timeouts, uv/npm/buildx caches
  - OCI labels, provenance and SBOM; job summary + GitHub Deployment record
  - CI only calls `make`
- **Rules:**
  - Migrations stay backward-compatible (expand, then contract), so a rollback works.
  - Each deploy causes a few seconds of downtime per service.
  - CI never commits to the repo.

## Kubernetes-ready by construction
| Now (compose) | Later (Kubernetes) |
|---|---|
| env-only config, one process per container | Deployment + ConfigMap/Secret, same names |
| `/api/healthz` + `/api/readyz` | liveness / readiness probes |
| `*-migrate` one-shot services | Job / ArgoCD Sync hook |
| service names `backend-ot` etc. | Service DNS, unchanged |
| compose resource limits | requests / limits |
| non-root images, `:<sha>` tags | same images |
| sops secrets | External Secrets Operator (GCP Secret Manager), same keys |
| build job separate from deploy job | swap only the deploy job |

## Where every secret goes
| Secret | Dev (laptop) | Prod source of truth (git, encrypted) | Prod on the VM | GitHub |
|---|---|---|---|---|
| backend-ot `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | `services/backend-ot/.env` (gitignored) | `deploy/prod/secrets/backend-ot.sops.env` | `/opt/pae/secrets/backend-ot.env` (root, 0600) | none |
| intelli-gateway `ANTHROPIC_API_KEY`, `OPEN_METEO_API_KEY`, `DATABASE_URL` | `services/intelli-gateway/.env` | `deploy/prod/secrets/intelli-gateway.sops.env` | `/opt/pae/secrets/intelli-gateway.env` | none |
| powerflow `DATABASE_URL` | `services/powerflow/.env` | `deploy/prod/secrets/powerflow.sops.env` | `/opt/pae/secrets/powerflow.env` | none |
| Postgres container passwords | compose defaults | in each service's sops file | same | none |
| `GHCR_READ_TOKEN` (fine-grained PAT, `read:packages`) | none | `deploy/prod/secrets/host.sops.env` | `/root/.docker/config.json` | none |
| `RESTIC_PASSWORD` (repository encryption key) | none | `deploy/prod/secrets/host.sops.env` | `/opt/pae/secrets/backup.env` | none |
| **GCS access for backups** | none | **no key**: the VM's attached service account `pae-prod-vm@…`, `roles/storage.objectAdmin` **on the backup bucket only**. restic's `gs:` backend uses it through the metadata server. | (none on disk) | none |
| **age private key** | `~/.config/sops/age/keys.txt` + a password-manager copy | never in git (public key in `.sops.yaml`) | not stored | Environment `production` → `SOPS_AGE_KEY` |
| Tailscale CI | none | none | none | Environment `production` → `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET` |
| Tailscale VM join key | none | none | used once by `host-setup.sh` | none |
| GCP for OpenTofu | your `gcloud auth application-default login` (no key file) | none | none | none (infra runs from your laptop only) |
| OpenTofu state | none | GCS state bucket (versioned), not git | none | none |
| GHCR push | none | none | none | built-in `GITHUB_TOKEN` |

- **The owner creates and edits the `*.sops.env` files by hand.** Claude never reads or edits credential files. Claude writes `.sops.yaml`, a `*.sops.env.example` per service listing only the key names, and the scripts.
- `deploy.sh` and `make prod-deploy` never decrypt into the working tree: `sops -d` streams to stdout over Tailscale SSH straight into `/opt/pae/secrets/`. `.gitignore` gets `deploy/prod/**/*.env` with `!*.sops.env`.
- Rotate a secret: `sops deploy/prod/secrets/<svc>.sops.env`, commit, `make prod-deploy`.
- `check-boundaries` (new check, Stage 5) verifies every `*.sops.env` is encrypted.
- The OpenTofu state bucket is restricted to your account; state can hold sensitive values.
- The VM service account has no other roles beyond the bucket (plus log/metric writer only if you later use Cloud Ops; Alloy doesn't need it).

## Monitoring (same on the GCP VM or on Kubernetes later)
- **Grafana Cloud free tier + the Alloy agent on the VM (recommended).** It shows per-container CPU, memory, restarts and network, VM CPU/RAM/disk/I/O, Postgres size and connections (`postgres_exporter`), and container logs. It survives the VM dying, and the same agent runs as a Helm chart on Kubernetes.
- The alternative is self-hosted Prometheus + Grafana + Loki on the VM: about 1 GB RAM, and it dies with the VM.
- **Alerts (Stage 9):**
  - disk above 80%
  - container restarting
  - `/readyz` failing
  - poll errors, plus an external heartbeat (healthchecks.io) in case the VM dies
- **Quick looks:** `make prod-status`, `make prod-logs svc=`, `make prod-stats`.

## Make targets (root Makefile → `deploy/prod/Makefile`; laptop needs `tofu`, `sops`, `tailscale`, `gcloud`)
| Command | Does |
|---|---|
| `make infra-plan` / `make infra-up` | OpenTofu plan / apply, then `host-setup.sh` |
| `make prod-deploy [RELEASE=<sha>]` | `deploy.sh` (the same thing CI runs) |
| `make prod-rollback` | redeploy `RELEASE.prev` |
| `make prod-status` / `prod-logs svc=` / `prod-stats` | health / logs / live CPU and memory |
| `make prod-backup` / `prod-restore [SNAPSHOT=]` | `pg_dump` + restic now / restore |
| **`make prod-pause`** | back up, then **stop the VM**. Compute stops billing; disks and snapshots are still billed (about $9). A reserved static IP on a stopped VM bills at the higher idle rate (about $7.30), for about **$17/month** at 1 site. Since access is Tailscale-only with no public ports, the static IP is optional until Stage 4's public domain; dropping it saves about $3.65 running or $7.30 paused. |
| **`make prod-resume`** | start the VM, wait for Tailscale, deploy the last release, check health |
| **`make prod-destroy CONFIRM=prod`** | `tofu destroy` everything except the backup bucket and state bucket; `KEEP_BACKUPS=no` also deletes those (asks again) |

- Destructive targets need `CONFIRM=prod` and always take a fresh backup first.
- The dev `make down` / `down-all` never touch prod.
- While paused, sites aren't polled, so the data has gaps.

## Switching providers
Only `deploy/infra/<provider>/` and the restic repository URL are provider-specific. Everything else (compose, configs, sops secrets, CI/CD, Tailscale site routers) is identical.

A move takes about half a day plus a short downtime:
1. Provision.
2. `host-setup.sh`.
3. Restore the DBs.
4. `deploy.sh`.
5. Switch DNS or the Tailscale name.

---

## Master plan (stages)
New host and CI tools, each needing your OK when its stage starts (none is a service library dependency): Tailscale, sops + age, restic, OpenTofu, Caddy, Grafana Alloy (+ a Grafana Cloud free account).

| Stage | Work |
|---|---|
| **0 Cleanup** | Section above |
| **1 Readiness** | Done: pinned `postgres:16.15-alpine` everywhere, intelli-gateway `/api/readyz`, nginx resolver + variable upstreams |
| **2 CI** | `ci.yml` + reusable workflows; required checks on `main`; images to GHCR as `:<sha>` |
| **3 Infra** | `deploy/infra/gcp/main.tf`: e2-standard-2, 20 GB boot, 50 GB pd-balanced data disk, static IP, daily snapshot schedule (7 kept), backup bucket (different region, e.g. us-east1), state bucket, least-privilege VM service account, firewall (no public ports). `make infra-plan/up`. |
| **4 Access** | Tailscale-only access first; later a public domain + Caddy + oauth2-proxy, then real app auth (needed before the mobile app) |
| **5 Prod stack** | `compose.prod.yaml`, configs, sops secrets, nightly restic backups; test a restore once |
| **6 Site links** | Playbooks: (a) Tailscale/WireGuard subnet router, (b) direct static IP + allow-list, (c) on-site backend-ot with the same compose. Verify with `/api/health_modbus_client`. |
| **7 CD** | `deploy-prod.yml` + `deploy.sh`; manual deploy first, then CI; rehearse a rollback |
| **8 Cost controls** | `prod-pause` / `resume` / `destroy`; rehearse pause → resume → restore |
| **9 Operations** | Alloy → Grafana Cloud, `postgres_exporter`, the alerts above, app `/metrics` (dependency: ask first), runbook (deploy, rollback, restore, rotate, add a site) |

## Future path: Option B (GKE Autopilot + Cloud SQL), about 1–2 weeks
1. **Middle step, A + Cloud SQL (about 1–2 days):**
   - Create Cloud SQL PG 16 (ENTERPRISE, e.g. `db-custom-1-3840`) with private IP in the VM's VPC (or the Cloud SQL Auth Proxy container).
   - `pg_dump`/restore, then point `POSTGRES_HOST`/`DATABASE_URL` at it.
   - Nothing in the schema is Cloud SQL-specific; it is core Postgres 16.
   - Drop the data disk and restic for that DB (Cloud SQL backups/PITR replace them).
2. Create the GKE Autopilot cluster (OpenTofu `deploy/infra/gke/`); keep GHCR or add Artifact Registry.
3. Write `deploy/k8s/base` + `overlays/prod` (kustomize) for the 4 services + Redis from `compose.prod.yaml`: probes, limits, `replicas: 1` where single-instance, migrate Jobs as ArgoCD Sync hooks.
4. Move secrets: sops values → GCP Secret Manager + External Secrets Operator (same key names).
5. Site connectivity: the Tailscale Kubernetes operator (egress proxy) or Cloud VPN.
6. Install ArgoCD; change `deploy-prod.yml` from "run deploy.sh" to "bump the image tag in the overlay".
7. Install Alloy with its Helm chart (same dashboards); cut over in a maintenance window; keep the VM for a week as a fallback.

---

## Verification
- **Stage 0:**
  - `make check` via the test-runner agent.
  - `make up` + `make e2e` (the dev stack still builds).
  - `git grep -nE 'k8s/|argocd|gcp_bootstrap|cloud\.ps1|DEPLOYMENT\.md|RUNBOOK'` shows only intended hits.
  - boundary-reviewer on the diff; the diff reviewed before commit.
- **Stage 1:** per service, its `make lint typecheck test` (+ `test-integration`), `make contract` with no unexpected diff, the dev stack up healthy and `make e2e-2bess-1pv` agreeing.
