# Per-service change map (toward a standard deploy/CI-CD framework)

The deploy + CI/CD setup in this repo is ~90% boilerplate. To reuse it for another
`pae-*` service, only a small set of **parameters** change. This file lists those
parameters and, file-by-file, exactly what to edit. Everything not listed is reusable
as-is.

> Convention: below, service-specific values are written as `{{TOKEN}}`. This repo's
> concrete value for each is in the table. When you templatize this into a real
> framework (cookiecutter / copier / Helm), these tokens are your variables.

---

## 1. The service parameters (the only things that really differ)

| Token | This service | Where it comes from | Notes |
|---|---|---|---|
| `{{SERVICE}}` | `pae-backend-ot` | you choose | k8s object names, labels, image name, ArgoCD app |
| `{{APP_MODULE}}` | `app:app` | code layout | uvicorn target; `{{IMPORT}}` = `from app import app` |
| `{{PORT}}` | `8000` | app | container + Service port |
| `{{GH_REPO}}` | `yazdanimehrdad1/pae-backend-ot` | GitHub | WIF condition, ArgoCD `repoURL`, CD |
| `{{GCP_PROJECT}}` | `prd-pae-backend-ot` | GCP | project ID |
| `{{REGION}}` | `us-central1` | GCP | |
| `{{AR_IMAGE}}` | `{{REGION}}-docker.pkg.dev/{{GCP_PROJECT}}/pae/{{SERVICE}}` | Artifact Registry | image path |
| `{{NAMESPACE}}` | `pae-backend-ot-prod` | you choose | k8s namespace |
| `{{SQL_INSTANCE}}` | `pae-backend-ot-pg-prod` | Cloud SQL | |
| `{{SQL_CONN}}` | `{{GCP_PROJECT}}:{{REGION}}:{{SQL_INSTANCE}}` | Cloud SQL | proxy `INSTANCE_CONNECTION_NAME` |
| `{{DB_NAME}}` / `{{DB_USER}}` | `pae_backend_ot` / `pae_backend_ot_user` | Cloud SQL | |
| `{{KSA}}` | `pae-backend-ot` | you choose | k8s ServiceAccount |
| `{{GSA}}` | `pae-backend-ot-prod@{{GCP_PROJECT}}...` | GCP IAM | Workload Identity for the SQL proxy |
| `{{SECRET}}` | `pae-backend-ot-secrets` | k8s | app Secret name |
| `{{SM_DB_PASSWORD}}` | `pae-backend-ot-postgres-password` | Secret Manager | |
| `{{APP_ENV}}` | `AGGREGATOR_MODBUS_HOST`, `POLL_*`, … | app | app-specific config keys/values |
| `{{HEALTH_PATH}}` / `{{READY_PATH}}` | `/api/healthz` / `/api/readyz` | app | probe paths |

**Capabilities that vary per service** (include/drop the relevant files):
- Needs a **database** (Cloud SQL + proxy sidecar + migrations)? — keep `migration-job.yaml`,
  the proxy sidecar, `{{SQL_*}}`. If not, delete them.
- Needs **Redis**? — keep `redis.yaml` + `REDIS_HOST`. If not, delete them.
- Needs **outbound** to a device/API (like Modbus here)? — that's just `{{APP_ENV}}`.

---

## 2. File-by-file change map

### Container
- **`docker/Dockerfile`** — reusable; change only: `PYTHONPATH` if not `src/` layout, the
  final `CMD ["uvicorn", "{{APP_MODULE}}", ...]`, `EXPOSE {{PORT}}`, `HEALTHCHECK` path
  `{{HEALTH_PATH}}`, and the `COPY` set if the repo dirs differ (`config/`, `scripts/`).
- **`docker/entrypoint.sh`** — reusable; change only if migrations differ (the
  `scripts/migrate_db.py` call) or the DB-wait import path. Drop entirely if no DB.

### CI/CD (`.github/workflows/`)
- **`ci.yml`** — mostly reusable. Change: the smoke-test import (`{{IMPORT}}`), and the
  `services:` block (postgres/redis) to match `{{APP_ENV}}` needs. Python version, ruff,
  kubeconform steps are generic.
- **`cd-prod.yml`** / **`cd-dev.yml`** — change: image name `{{SERVICE}}` in the image ref,
  overlay path if renamed. Branch triggers + WIF auth are generic (they read repo
  Variables/Secrets, so no per-service edit in the file itself).

### Kubernetes base (`k8s/base/`)
- **`kustomization.yaml`** — change: `configMapGenerator` literals (`{{APP_ENV}}`,
  `{{DB_NAME}}`, `{{DB_USER}}`, `{{HEALTH_PATH}}` implicitly), `images[].name`
  `{{SERVICE}}`, and the `labels` value. Structure is reusable.
- **`deployment.yaml`** — change: name/labels `{{SERVICE}}`/`app: {{SERVICE}}-api`,
  `image: {{SERVICE}}`, `containerPort {{PORT}}`, probe paths `{{HEALTH_PATH}}`/`{{READY_PATH}}`,
  resources. Keep/drop the `cloud-sql-proxy` initContainer per DB need.
- **`service.yaml`** — change: name `{{SERVICE}}`, `port {{PORT}}`, selector `app: {{SERVICE}}-api`.
- **`serviceaccount.yaml`** — change: name `{{KSA}}`, WIF annotation `{{GSA}}`.
- **`redis.yaml`** — keep only if the service uses Redis; names/labels are generic.
- **`migration-job.yaml`** — keep only if the service has migrations. Change: name,
  `image: {{SERVICE}}`, the `command` (migration entrypoint), proxy `INSTANCE_CONNECTION_NAME`.
  ArgoCD hook + sync-wave annotations are reusable.
- **`hpa.yaml`** / **`pdb.yaml`** — change: name `{{SERVICE}}`, min/max, selector label.

### Kubernetes overlay (`k8s/overlays/prod/kustomization.yaml`)
Per-service AND per-environment — the highest-density file:
- `namespace: {{NAMESPACE}}`
- `images[].newName: {{AR_IMAGE}}` (CI sets `newTag`)
- `replicas`, resource patch numbers
- proxy `INSTANCE_CONNECTION_NAME: {{SQL_CONN}}` (×2: Deployment + Job)
- ServiceAccount annotation `{{GSA}}`
- HPA min/max
- app-specific config overrides (`{{APP_ENV}}`, e.g. `AGGREGATOR_MODBUS_HOST`)

### ArgoCD (`k8s/argocd/application-prod.yaml`)
- `metadata.name: {{SERVICE}}-prod`
- `source.repoURL: https://github.com/{{GH_REPO}}.git`
- `source.path` (overlay path), `destination.namespace: {{NAMESPACE}}`
- syncPolicy is reusable.

### Scripts & tooling
- **`scripts/gcp_bootstrap.sh`** — change the vars block at top: `PROJECT_ID`,
  `GITHUB_REPO`, `SQL_INSTANCE`, `REDIS_INSTANCE`, `K8S_NAMESPACE`, `KSA`, GSAs, AR repo.
  The gcloud command *sequence* is reusable.
- **`Makefile`** / **`make.ps1`** — change the cloud-control vars: `GCP_PROJECT`,
  `SQL_INSTANCE`, `K8S_NS` (and the hardcoded strings in the `make.ps1` cloud cases).
  Everything else is generic.

### Docs
- **`docs/RUNBOOK.md`**, **`docs/DEPLOYMENT.md`** — these embed concrete values throughout.
  In a real framework these become templated docs (or a shared runbook + a short
  per-service "values" page). For now, treat every concrete name above as a token.

---

## 3. Reusable as-is (no per-service edits)
- `.github/workflows/ci.yml` structure (lint/test/build/kubeconform steps)
- ArgoCD hook + sync-wave strategy in `migration-job.yaml` / `deployment.yaml`
- The Cloud SQL Auth Proxy sidecar pattern, probe strategy, security contexts
- The scale-to-zero `cloud-down`/`cloud-up` logic (only the *vars* differ)
- Branch → environment model and the GitOps flow

---

## 4. When you templatize this (the "framework")
Recommended path once 2–3 services share this shape:
1. Extract `k8s/base/` + workflow templates into a **shared template** (cookiecutter/copier
   variables = the tokens in §1), or a **Helm chart** with a per-service `values.yaml`.
2. Keep per-service repos tiny: a `values`/`answers` file + app code; render the rest.
3. Centralize the runbook; each service keeps only its §1 parameter table.
4. Consider an **ApplicationSet** in ArgoCD to generate the per-service `Application`s
   from one template instead of hand-written `application-*.yaml`.
