# Production deployment: clean slate + master plan (rev. 3)

## Context
The only deployment work in the repo is backend-ot's old GKE + ArgoCD + Cloud SQL setup. It predates the monorepo:
- ArgoCD points at the old repo.
- The service-level `.github/` is inert, and `ci.yml` is broken.
- It covers one service only.
- It never solved how the cloud reaches site Modbus devices.

It gets removed, the useful lessons are kept, and production is rebuilt from scratch for backend-ot, intelli-gateway, powerflow and web-plusdas. mobile-plusdas is excluded, and mock-modbus stays dev only.

Constraints:
- 1 site to start, designed for multiple sites, few users.
- Three environments: **local** (the laptop, `make up`), **dev** (a cloud mirror of prod with non-client data) and **prod** (real sites and clients).
- Site links can be VPN, direct, through the RTAC aggregator, or backend-ot on site.
- Kubernetes/GKE must stay an easy later step.

Each stage starts only after the owner approves it. Cost figures are estimates from GCP list prices; check them in the GCP pricing calculator.

**Current status, day-to-day use and the go-live checklist: [`STATUS.md`](STATUS.md).**

## Decisions (rev. 3)
| # | Decision |
|---|---|
| Platform | **Option A on GCP:** one VM, Docker Compose, in project `pae-platform-prod`. e2-standard-2, us-central1, 20 GB boot disk, 50 GB pd-balanced data disk, no external IP until Stage 4 (IAP for access, Cloud NAT for outbound), daily snapshots, GCS backup bucket. |
| Tooling | **GCP-native** (rev. 3): only `gcloud` on the laptop; Secret Manager, Artifact Registry, Workload Identity Federation, IAP, Ops Agent. See "Tooling". |
| Database | **Plain PostgreSQL 16**, the same image in dev and prod. No TimescaleDB. |
| Historian | **No retention work**: readings are kept indefinitely in one plain table; storage is handled by growing the data disk. This plan covers deployment only. |
| Environments | **local** = laptop Docker (`make up`). **dev** = `pae-development`, VM `pae-dev` (e2-medium, 30 GB data disk; **public over HTTP at http://136.115.89.60 since 2026-10-26 for demos**, see `STATUS.md`): same images, compose file and setup as prod, only simulated/test sites, deployed automatically on every merge to `main`. **prod** = `pae-platform-prod`, VM `pae-prod`: real sites, deployed the same commit only after the owner approves. **Prod VM stopped 2026-10-25 to save cost** (about $8/month for disks and snapshots); everything is set up, and only dev is deployed until go-live. |

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
| Cloud NAT gateway + traffic (no static IP until Stage 4; see "Cost changes from GCP-native") | about $1–2 |
| Boot-disk snapshots (about 8 GB used @ $0.05/GB) | about $0.40 |
| Backup bucket, platform part (other 2 DBs, configs; under 2 GB @ $0.020/GB) | about $0.05 |
| Network egress (logs and metrics stay inside Google; internet traffic goes through Cloud NAT) | about $0–1 |
| Secret Manager, Artifact Registry, IAP, Ops Agent (free allotments for one VM) | about $2–4 |
| **Platform total** | **about $55** (**about $37** with a 1-year CUD) |

**(b) Database storage cost.** It grows with the data. Each stored GB costs about **$0.16/month** all-in:
- data disk $0.10 (pd-balanced, provisioned with headroom below the 80% alert)
- daily snapshots, 7 kept, about $0.05
- weekly `pg_dump` copies in GCS, about $0.01

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

**(c) dev environment** (`pae-development`, on top of prod's figures):

| Item | Monthly |
|---|---|
| VM e2-medium (2 shared vCPU, 4 GB) | about $24.50 (1-year CUD about $15) |
| Boot 20 GB + data 30 GB pd-balanced | $5.00 |
| Snapshots, Cloud NAT, Secret Manager | about $2–3 |
| **dev total** | **about $32** (about $23 committed); about $8 while stopped (disks and snapshots only) |

Dev data is test data, so its disk grows only with the simulated sites you load. Prod plus dev: about **$94/month** for 1 site in month 1 (about $66 committed).


---

## Stage 0 (done 2026-10-24): remove the old deployment and keep the lessons
*Record of what Stage 0 did. Rev. 3 (2026-10-25) replaced its sops-file rules with Secret Manager ones in root `CLAUDE.md` and the boundary-reviewer.*
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
- `services/mock-modbus/CLAUDE.md:4`: "never in a production manifest (k8s, overlays…)" → name `deploy/cloud/`, `deploy/infra/`, `deploy/k8s/`, root `.github/` deploy workflows.
- **Keep:** `POD_NAME` and leader election (`src/config.py`, `src/scheduler/locks.py`), and the Dockerfile and entrypoint (dev uses them).
- **Leave:** the `/readyz` docstring in `src/api/routers/health.py` (avoids contract and client churn).
- **Root `CLAUDE.md`:**
  - `:44-48`: the "Deployment is out of scope" rule becomes "Production deployment lives in `deploy/cloud/` + `deploy/infra/` (see `deploy/PLAN.md`). These coordinate services only through images, env and `make -C`, never through paths into a service directory (no `include`/`extends` of `services/*/compose.yaml`, no `../services/...`)."
  - "Its config is its own `.env`": add "in dev; in prod, `deploy/cloud/config/<svc>.env` + `deploy/cloud/secrets/<svc>.sops.env`".
  - web-plusdas rule: the root coordinates it through the Makefile, `deploy/compose/`, `deploy/cloud/` and root `.github/`.
  - mock-modbus rule: forbidden in `deploy/cloud/`, `deploy/infra/`, `deploy/k8s/` and the root deploy/build workflows.
- **`.claude/agents/boundary-reviewer.md`:**
  - `:33`: same update as the mock-modbus rule.
  - `:36`: allow committed sops-encrypted `*.sops.env` files; flag any secrets file without a `sops:` block or `ENC[` values.
  - `:38-40`: replace the out-of-scope list.
- **`scripts/check_boundaries.py`:**
  - Dev-only scan (`:17,199-204`): **keep its current scope, all of `deploy/` except `deploy/compose/`**, so the future `deploy/k8s/` is covered. Skip `*.md` (docs aren't manifests; `deploy/PLAN.md` mentions mock-modbus by name). Add the root `.github/workflows/deploy-prod.yml` and `_build-image.yml`, but **not** `ci.yml`, which legitimately tests mock-modbus.
  - Outside-in check: add `deploy/prod` and `deploy/infra` to `SHARED_DIRS` (`:39`), so a `../services/...` path there is caught.
  - ~~New check in Stage 5: every `*.sops.env` is encrypted.~~ Superseded by rev. 3: secrets live in Secret Manager, there are no sops files.
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

## Tooling: GCP-native (decided 2026-10-25)
Only `gcloud` on the owner's laptop. GCP's own services replace the provider-neutral tools of rev. 2:

| Need | Uses |
|---|---|
| Create the VM, disks, buckets, firewall, identities | `deploy/infra/gcp/bootstrap.sh` (gcloud, idempotent: each step checks before it creates) |
| Prod secrets | **Secret Manager**. The VM reads them with its own service account at deploy time; neither CI nor git ever holds a secret value |
| Container images | **Artifact Registry** `us-central1-docker.pkg.dev/pae-platform-prod/pae/pae-<svc>:<git sha>`. CI pushes through Workload Identity Federation; the VM pulls with its service account (no token) |
| CI → GCP auth | **Workload Identity Federation** (GitHub OIDC), limited to this repository; no JSON keys anywhere |
| Shell and deploy access, no public ports | **IAP TCP forwarding**: `gcloud compute ssh pae-prod --tunnel-through-iap` (owner and CD) |
| Backups | Daily snapshots of both disks (7 kept), plus a weekly `pg_dump` of each database to the GCS backup bucket (in another region) |
| Monitoring | **Ops Agent** → Cloud Monitoring and Logging: VM CPU/RAM/disk, container logs, uptime check, alert policies |
| User access to the UI (until Stage 4 decides public HTTPS) | An IAP tunnel to port 80 (`make ui env=prod` opens http://localhost:8080) |
| Site VPN | Decided in Stage 6: WireGuard on the VM (built into Linux) or Tailscale |

The Docker Compose stack, the images and CI stay provider-neutral. Leaving GCP later would mean replacing the secrets, access and monitoring pieces (about a day's work).

## GCP projects
- **prod: `pae-platform-prod`** (created 2026-10-25) and **dev: `pae-development`** (existing, emptied and set up 2026-10-25); billing account `01E864-801659-7E4519`, region `us-central1`. The image registry and GitHub's Workload Identity Federation exist once, in prod; dev's VM pulls the same images. Each project has its own network, NAT, VM, disks, snapshots, secrets (separate random passwords and its own API keys) and backup bucket; the dev VM can read the registry but not prod's secrets or bucket (checked).
- Cleanup done the same day: the old project `prd-pae-rtac-server` (GKE `pae-autopilot`, Cloud SQL `rtac-pg-prod`) is deleted (recoverable until about 2026-11-24 with `gcloud projects undelete prd-pae-rtac-server`); `pae-development`'s idle NAT router and static IP are deleted. `pae-development` and `pae-shared` are empty and free; keep them as spares.
- `pae-shared` stays empty and free as a spare.

## How the deploy files are laid out
```
deploy/
  compose/                 (existing) dev stack, builds from source, includes mock-modbus
  cloud/                   dev and prod (the same files; env=dev|prod picks the settings)
    compose.yaml           the stack: image: ${REGISTRY}/pae-<svc>:${RELEASE}, never build:; volumes on
                           the data disk, healthchecks, memory limits, the backend-ot-migrate profile.
                           Self-contained: never include/extends services/*/compose.yaml and no
                           ../services/... paths; the local Modbus simulator never runs here.
    Makefile               infra-up, host-setup, deploy, status, logs, stats, backup, ssh, ui, seed-site
                           (all env=dev|prod; called from the root Makefile)
    config/dev.env|prod.env  non-secret settings per environment, committed
    scripts/               host-setup.sh, deploy.sh, backup.sh (run on the VM), ops-agent.yaml
  infra/
    gcp/bootstrap.sh       gcloud: APIs, VPC + firewall, Cloud NAT, service accounts, Artifact Registry,
                           buckets, Workload Identity Federation, VM + disks + snapshot schedule
    gcp/README.md          what it creates, how to run it, how to tear down
  k8s/                     (future) kustomize base + overlays/prod
  PLAN.md
```
- One release = one git SHA for all services.

## CI/CD
```
 PR ──► CI: changed services' make lint/typecheck/test + check-boundaries + contracts-check; build +
        smoke-test changed images (not pushed). Required check: "CI result"
 merge to main ──► CI: everything, then build + smoke-test all 4 images ──► push to Artifact Registry :<sha>
        ──► deploy-dev: automatic, the same steps on pae-dev ──► deploy-prod: waits for the owner's Approve (GitHub Environment "production"), same <sha>
        ──► auth to GCP (WIF) ──► IAP SSH to that environment's VM ──► deploy.sh <sha> on it:
             read secrets from Secret Manager ─► pre-deploy pg_dump ─► pull ─► backend-ot-migrate
             ─► up -d ─► health checks ─► OK: record RELEASE (keep RELEASE.prev) │ FAIL: redeploy RELEASE.prev
```
- **Workflows:** `ci.yml`, reusable `_service-ci.yml` and `_build-image.yml`, `deploy.yml` (dev automatically, then prod after approval; also `workflow_dispatch` with an environment and any SHA, which is how you roll back).
- **Path filters include contract consumers** (`scripts/ci/changed_services.py`, from `contracts/README.md`): a change to `contracts/openapi/backend-ot.openapi.json` also runs web-plusdas, mobile-plusdas and intelli-gateway; powerflow's and intelli-gateway's specs also run web-plusdas; an unknown contract runs everything. backend-ot, powerflow and intelli-gateway also run `make test-integration` (each service's own `compose.test.yaml` stack).
- **The image list is explicit:** the 4 prod services, never mock-modbus or mobile-plusdas. Each image builds from its own service directory, which keeps `git subtree split` intact.
- **Standards:**
  - least-privilege `permissions:` (only the push job gets `id-token: write`); actions pinned to commit SHAs; Dependabot
  - no secrets in GitHub at all (WIF needs only two non-secret repository variables)
  - concurrency groups (one run per commit on main), job timeouts, uv/npm/buildx caches
  - OCI labels, provenance and SBOM; job summary + GitHub Deployment record
  - every check is a `make` target (only the change selector and its unit tests run as plain scripts)
- **Rules:**
  - Migrations stay backward-compatible (expand, then contract), so a rollback works.
  - Each deploy causes a few seconds of downtime per service.
  - CI never commits to the repo.

## Kubernetes-ready by construction
| Now (compose) | Later (Kubernetes) |
|---|---|
| env-only config, one process per container | Deployment + ConfigMap/Secret, same names |
| `/api/healthz` + `/api/readyz` | liveness / readiness probes |
| `backend-ot-migrate` one-shot | Job / ArgoCD Sync hook |
| service names `backend-ot` etc. | Service DNS, unchanged |
| compose resource limits | requests / limits |
| non-root images in Artifact Registry, `:<sha>` tags | same images |
| Secret Manager | External Secrets Operator reading the same secrets |
| build job separate from deploy job | swap only the deploy job |

## Where every secret goes
| Secret | Dev (laptop) | Prod (Secret Manager in `pae-platform-prod`) | On the VM | GitHub |
|---|---|---|---|---|
| backend-ot `POSTGRES_PASSWORD` (Redis runs without AUTH, reachable only on the VM's internal Docker network) | `services/backend-ot/.env` (gitignored) | `backend-ot-postgres-password` | written by `deploy.sh` to `/opt/pae/secrets/backend-ot.env` (root, 0600) | none |
| intelli-gateway `ANTHROPIC_API_KEY`, `OPEN_METEO_API_KEY`, its DB password | `services/intelli-gateway/.env` | `intelli-gateway-anthropic-api-key`, `intelli-gateway-open-meteo-api-key`, `intelli-gateway-postgres-password` | `/opt/pae/secrets/intelli-gateway.env` | none |
| powerflow DB password | `services/powerflow/.env` | `powerflow-postgres-password` | `/opt/pae/secrets/powerflow.env` | none |
| Image pulls | none | none: the VM service account has `artifactregistry.reader` | none | none |
| Backups to GCS | none | none: the VM service account has `storage.objectAdmin` on the backup bucket only | none | none |
| CI → GCP | none | none: Workload Identity Federation, attribute condition = this repository | none | repository variables `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_CI_SERVICE_ACCOUNT` (not secret) |

- **The owner adds the API-key values** (`gcloud secrets versions add <name> --data-file=-`, typed into the terminal, or in the console). Claude creates the empty secrets and the scripts, never the values. `bootstrap.sh` generates the three Postgres passwords itself (`openssl rand`, piped straight into Secret Manager), so nobody sees them.
- `deploy/cloud/scripts/deploy.sh` maps each secret to its service's env file in `/opt/pae/env/` (root, 0600); optional secrets without a value (the API keys) are left out instead of set empty.
- Rotate a secret: add a new version, then `make deploy env=...` (a database password change also needs `ALTER USER` first).
- Service accounts (least privilege):
  - `pae-prod-vm`: `secretmanager.secretAccessor` on the listed secrets, `artifactregistry.reader` on the repository, `storage.objectAdmin` on the backup bucket, `logging.logWriter` and `monitoring.metricWriter`.
  - `pae-ci`: `artifactregistry.writer` on the repository; for CD (Stage 7) also `iap.tunnelResourceAccessor`, `compute.osAdminLogin` on the VM, and `iam.serviceAccountUser` on `pae-prod-vm`.

## Monitoring
- **Ops Agent** on the VM: CPU, memory, disk, disk I/O, network, and every container's logs into Cloud Logging. Inside Cloud Monitoring's free allotment for one VM.
- **Per-container CPU/memory:** `make prod-stats` (`docker stats` over IAP SSH) for now; if needed later, cAdvisor's metrics through the Ops Agent's Prometheus receiver.
- **Postgres:** the Ops Agent's PostgreSQL receiver (size, connections).
- **Alerts (Stage 9):** disk above 80%, VM down, a container restarting (log-based metric), `/api/readyz` failing (from the VM's own check, written to Cloud Logging), backend-ot poll errors.
- **Quick looks:** `make status env=...`, `make logs env=... svc=`, `make stats env=...`.

## Make targets (root Makefile → `deploy/cloud/Makefile`; the laptop needs only `gcloud` and Git Bash, which brings bash, openssl and coreutils)
| Command | Does |
|---|---|
| `make infra-up env=prod|dev` | `deploy/infra/gcp/bootstrap.sh` (idempotent; safe to re-run) |
| `make ssh env=prod|dev` | IAP SSH to that VM |
| `make ui env=prod|dev` | IAP tunnel to that VM's port 80 → http://localhost:8080 |
| `make deploy env=prod|dev [RELEASE=<sha>]` | `deploy.sh` on the VM (the same thing CD runs) |
| `make rollback env=...` | redeploy `RELEASE.prev` |
| `make status env=...` / `logs env=... svc=` / `stats env=...` | health / logs / live CPU and memory |
| `make backup env=...` / `restore env=...` | `pg_dump` to GCS now / restore one |
| **`make pause env=...`** | back up, then **stop the VM**. Compute stops billing; disks and snapshots are still billed (about $9 at 1 site). The VM has no external IP until Stage 4 (IAP needs none), so nothing extra. |
| **`make resume env=...`** | start the VM, deploy the last release, check health |
| **`make destroy env=... CONFIRM=<env>`** | delete the VM, disks, snapshots, registry and secrets, keeping the backup bucket; `KEEP_BACKUPS=no` also deletes it (asks again) |

- Destructive targets need `CONFIRM=<env>` matching `env=` and always take a fresh backup first.
- The dev `make down` / `down-all` never touch prod.
- While paused, sites aren't polled, so the data has gaps.

## Cost changes from GCP-native
- **No static IP until Stage 4:** IAP needs no external address. Outbound internet (image pulls, the Claude API, Open-Meteo, Modbus to sites) goes through Cloud NAT: about $1/month for the gateway plus $0.045/GB processed. Net about −$2.50/month against the static IP.
- **Secret Manager:** about $0.06 per secret version per month, under $1. **Artifact Registry:** about $0.10/GB-month; a cleanup policy keeps the last 30 releases, about $1–3/month. **Ops Agent / Cloud Logging:** inside the free allotments for one VM (50 GiB logs).
- The cost totals above stay within about ±$2/month.

---

## Master plan (stages)
| Stage | Work |
|---|---|
| **0 Cleanup** | Done (section above) |
| **1 Readiness** | Done: pinned `postgres:16.15-alpine` everywhere, intelli-gateway `/api/readyz`, nginx resolver + variable upstreams |
| **2 CI** | Done: `ci.yml` + reusable `_service-ci.yml` / `_build-image.yml`, `scripts/ci/` (changed-service selection, image smoke tests), Dependabot for actions. **Owner step:** require the single check "CI result" on `main`. Image pushes go to Artifact Registry (Stage 3) |
| **3 Infra** | **Done 2026-10-25** (`make infra-up env=prod`, `make ssh env=prod` verified). `deploy/infra/gcp/bootstrap.sh`: APIs, removal of the auto-created `default` network (its rules opened SSH/RDP to the internet), VPC + firewall (IAP range only), Cloud NAT, service accounts, Artifact Registry (+ cleanup policy), backup bucket (us-east1), Secret Manager secrets, WIF for this repository, VM e2-standard-2 (20 GB boot, 50 GB data disk, no external IP), daily snapshot schedule (7 kept). CI image push switched to Artifact Registry. **dev** (`pae-development`, VM `pae-dev`, e2-medium, 30 GB data disk) from the same script with `env=dev`; it pulls the same images from prod's registry |
| **4 Access** | IAP tunnel for the owner first (`make ui env=prod|dev`); later a public domain with HTTPS and login, then real app auth (needed before the mobile app). Decide the HTTPS front then |
| **5 Stack** | **Done on dev 2026-10-25** (prod: same files, deployed at go-live). `deploy/cloud/compose.yaml`, `config/dev.env` + `prod.env`, `scripts/host-setup.sh` (data disk, Docker, registry login, Ops Agent, weekly backup timer), `scripts/deploy.sh` (Secret Manager → env files, pre-deploy backup, pull, migrate, up --wait, checks through the UI origin, auto-rollback), `scripts/backup.sh` (pg_dump → GCS). `make host-setup / deploy / status / logs / stats / backup env=...`, `make cloud-seed-site env=dev SITE=...`. Verified: dev deploy green, UI through IAP, container logs in Cloud Logging, `2bess_1pv` seeded, the e2e check AGREE on all 9 devices |
| **6 Site links** | Playbooks: (a) WireGuard or Tailscale to the site router, (b) direct static IP + allow-list (needs a static egress IP on the NAT), (c) on-site backend-ot with the same compose. Verify with `/api/health_modbus_client` |
| **7 CD** | **Done 2026-10-26**: first automatic deploy of `ce69a5a` to dev green (two fixes on the way: `CLOUDSDK_CORE_ACCOUNT` for OS Login under WIF, uploads into each SSH user's home). `.github/workflows/deploy.yml` + reusable `_deploy-env.yml`: after CI succeeds on a push to `main`, **dev** gets that SHA automatically (`make deploy env=dev RELEASE=<sha>` on the runner: WIF, then IAP SSH as `pae-ci` with OS Login, then `deploy.sh`). **prod** waits for approval in the GitHub Environment `production`; it follows dev only while the repository variable `PROD_AUTO_PROMOTE` is `true` (set at go-live), otherwise only by hand (Actions → Deploy → Run workflow). Rollback = Run workflow with an older SHA. `bootstrap.sh` grants `pae-ci` IAP tunnel, OS Admin Login, compute viewer and service-account-user on the VM account, per project |
| **8 Cost controls** | `pause` / `resume` / `destroy` (per environment); rehearse pause → resume → restore |
| **9 Operations** | Ops Agent dashboards and the alerts above, runbook (deploy, rollback, restore, rotate a secret, add a site) |

## Future path: Option B (GKE Autopilot + Cloud SQL), about 1–2 weeks
1. **Middle step, A + Cloud SQL (about 1–2 days):** Cloud SQL PG 16 (ENTERPRISE, e.g. `db-custom-1-3840`) with private IP in the VM's VPC; `pg_dump`/restore; point `POSTGRES_HOST`/`DATABASE_URL` at it. Nothing in the schema is Cloud SQL-specific. Its backups/PITR replace the data disk and dumps for that DB.
2. GKE Autopilot cluster in the same project; images already in Artifact Registry.
3. `deploy/k8s/base` + `overlays/prod` (kustomize) from `deploy/cloud/compose.yaml`: probes, limits, `replicas: 1` where single-instance, the migrate Job as an ArgoCD Sync hook.
4. Secrets: External Secrets Operator reading the same Secret Manager secrets.
5. Site connectivity: Cloud VPN or the Tailscale Kubernetes operator.
6. ArgoCD; `deploy.yml` changes from "run deploy.sh" to "bump the image tag in the overlay".
7. Monitoring: GKE's built-in Cloud Monitoring; cut over in a maintenance window; keep the VM a week as a fallback.

---

## Verification
- **Stage 0:** `make check`; `make up` + `make e2e`; `git grep` for the removed files shows only intended hits; boundary-reviewer on the diff.
- **Stage 1:** per service, its `make lint typecheck test` (+ `test-integration`), `make contract` with no unexpected diff, the dev stack up healthy and `make e2e-2bess-1pv` agreeing.
- **Stage 2:** the first PR run green on GitHub; then a push to main pushes the 4 images.
- **Stage 3:** `bootstrap.sh` runs twice with the second run changing nothing; `make ssh env=...` works through IAP; the VM has no external IP; the firewall allows only Google's IAP range.
