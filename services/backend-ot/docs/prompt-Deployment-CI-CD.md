

=== PROMPT STARTS HERE ===

## 0. Your role and the goal

You are setting up **production deployment and CI/CD** for the Python service in this
repo. The target architecture is GitOps on GKE, identical in shape to the reference
service `pae-backend-ot`. Do not invent a different architecture — reproduce this one,
adapted to what this service actually needs.

**The one idea:** *git is the source of truth for what runs in the cluster.* GitHub
Actions never touches the cluster. It builds an image, pushes it to a registry, and
writes the image **tag** back into git. ArgoCD, running inside the cluster, notices the
commit and makes the cluster match. A deploy is a commit; a rollback is a commit.

```
push to main ──► CI (lint, test, build, kubeconform)        [never touches the cluster]
             ──► CD (build+push image :<git-sha> to Artifact Registry,
                     kustomize edit set image in overlays/prod, commit "[skip ci]")
                                     │
                                     ▼
                    ArgoCD watches k8s/overlays/prod ──► syncs GKE
                       wave 1: migration Job  →  wave 2: Deployment  →  wave 3: HPA/PDB
```

Two things flow on two paths and meet at the cluster: the **image bytes** go to Artifact
Registry; only the **image name/tag** goes into git. That separation is exactly why no
cluster credentials ever live in GitHub.

**Work in this order.** Do not skip to writing YAML.

1. Survey the repo (§1).
2. Collect/confirm the parameters (§2) and the capability decisions (§3).
3. Make the app deployment-ready (§4) — probes, config, migrations.
4. Write the files (§5–§11), using the templates verbatim with tokens substituted.
5. Write the infra bootstrap script and docs (§12–§13).
6. Run the local verification gauntlet (§14) and report honestly (§16).

**Rules of engagement**
- Ask before adding any Python dependency.
- Never commit or push unless explicitly asked. Staging is fine.
- Never read or edit `.env*` or any file holding credentials.
- No secret value goes into git — not in a manifest, not in the overlay, not in the image.
- Show the diff before declaring a task done. Never claim something works unless you ran
  it; if you could not run it (no Docker, no gcloud, no cluster), say so plainly and mark
  it unverified.

---

## 1. First: survey this repo, do not assume

Before writing anything, establish the facts and report them back in a short table:

| Question | How to find out |
|---|---|
| Python version | `pyproject.toml` `requires-python`, any `.python-version`, existing Dockerfile |
| Dependency manager | Is there `uv.lock` (uv), `poetry.lock` (poetry), `requirements.txt`, or just `pyproject.toml` + pip? **Match what the repo already uses — do not migrate it as a side effect.** |
| Import layout | Flat modules under `src/` needing `PYTHONPATH=src`? Or a real installed package (`src/<pkg>/`)? This decides `PYTHONPATH`, the uvicorn target, and the smoke test. |
| ASGI app object | `grep -rn "FastAPI(" src/` → gives `{{APP_MODULE}}` (e.g. `app:app`, `myservice.main:app`) |
| Port | Existing Dockerfile/compose/config default |
| Health endpoints | Does a dependency-free liveness route exist? A readiness route that checks deps? (§4.1) |
| Datastores | Postgres? Redis? Neither? Something else (Mongo, Kafka, GCS)? |
| Migrations | Raw SQL runner script, Alembic, or none? What is the exact command? |
| Existing lint/format/type config | `[tool.ruff]`, `[tool.black]`, `[tool.mypy]`, pyright, pre-commit |
| Existing CI | Anything already in `.github/workflows/` — extend rather than duplicate |
| Existing container/compose | `Dockerfile`, `docker-compose.yaml`, `Makefile`, `make.ps1` |
| Git remote + default branch | `git remote -v`, `git branch --show-current` |

**Explicitly list what this service does NOT need.** Every unused piece (Redis, Cloud
SQL, the migration Job) must be *deleted*, not carried along commented-out.

---

## 2. Parameters — collect these before writing files

These are the only things that genuinely differ between services. Ask the user for any
you cannot infer; propose a sensible default for each and let them correct you. Record
the final table in `docs/DEPLOYMENT.md` when you are done.

| Token | Meaning | Reference value (`pae-backend-ot`) | Default to propose |
|---|---|---|---|
| `{{SERVICE}}` | Service name: k8s object names, labels, image name, ArgoCD app | `pae-backend-ot` | repo/package name, kebab-case |
| `{{APP_MODULE}}` | uvicorn target | `app:app` | from §1 |
| `{{IMPORT}}` | Smoke-test import line | `from config import settings; from app import app` | from §1 |
| `{{PORT}}` | Container + Service port | `8000` | `8000` |
| `{{PYTHONPATH}}` | In-image PYTHONPATH | `/app/src` | `/app/src` if flat layout, else unset |
| `{{GH_REPO}}` | `owner/repo` — WIF condition, ArgoCD repoURL | `yazdanimehrdad1/pae-backend-ot` | from `git remote -v` |
| `{{GCP_PROJECT}}` | GCP project **ID** (not number) | `prd-pae-backend-ot` | ask |
| `{{REGION}}` | GCP region | `us-central1` | `us-central1` |
| `{{AR_HOST}}` | Artifact Registry host | `us-central1-docker.pkg.dev` | `{{REGION}}-docker.pkg.dev` |
| `{{AR_REPO}}` | Artifact Registry repo (shared across services) | `pae` | `pae` |
| `{{AR_IMAGE}}` | Full image path | `{{AR_HOST}}/{{GCP_PROJECT}}/{{AR_REPO}}/{{SERVICE}}` | derived |
| `{{CLUSTER}}` | GKE cluster | `pae-autopilot` | `pae-autopilot` |
| `{{NAMESPACE}}` | k8s namespace | `pae-backend-ot-prod` | `{{SERVICE}}-prod` |
| `{{SQL_INSTANCE}}` | Cloud SQL instance | `pae-backend-ot-pg-prod` | `{{SERVICE}}-pg-prod` |
| `{{SQL_CONN}}` | `PROJECT:REGION:INSTANCE` for the proxy | `prd-pae-backend-ot:us-central1:pae-backend-ot-pg-prod` | derived |
| `{{DB_NAME}}` / `{{DB_USER}}` | Postgres db + user | `pae_backend_ot` / `pae_backend_ot_user` | from app config |
| `{{KSA}}` | k8s ServiceAccount | `pae-backend-ot` | `{{SERVICE}}` |
| `{{GSA}}` | GCP SA the KSA impersonates (Cloud SQL client) | `pae-backend-ot-prod@{{GCP_PROJECT}}.iam.gserviceaccount.com` | `{{NAMESPACE}}@…` |
| `{{DEPLOYER_GSA}}` | GCP SA GitHub Actions impersonates | `gh-deployer@{{GCP_PROJECT}}.iam.gserviceaccount.com` | `gh-deployer@…` |
| `{{SECRET}}` | k8s Secret name | `pae-backend-ot-secrets` | `{{SERVICE}}-secrets` |
| `{{CONFIGMAP}}` | k8s ConfigMap name | `pae-backend-ot-config` | `{{SERVICE}}-config` |
| `{{SM_DB_PASSWORD}}` | Secret Manager entry for the DB password | `pae-backend-ot-postgres-password` | `{{SERVICE}}-postgres-password` |
| `{{HEALTH_PATH}}` / `{{READY_PATH}}` | Liveness / readiness paths | `/api/healthz` / `/api/readyz` | match this service's router prefix |
| `{{APP_LABEL}}` | Extra pod label so the Service targets only app pods | `pae-backend-ot-api` | `{{SERVICE}}-api` |
| `{{MIGRATE_CMD}}` | Migration command | `["python", "scripts/migrate_db.py"]` | from §1 |
| `{{APP_ENV}}` | Service-specific non-secret env keys | `AGGREGATOR_MODBUS_HOST`, `POLL_*` | from `.env.example` / config |
| `{{RUFF_VERSION}}` | Pinned ruff tag, shared by CI + hook + make | `0.16.0` | latest stable, pinned |

---

## 3. Capability decisions — include or delete

Ask the user; do not guess. Each answer adds or removes whole files.

| Capability | If **yes**, keep | If **no**, delete |
|---|---|---|
| **Postgres / Cloud SQL** | `cloud-sql-proxy` initContainer in Deployment + Job, `{{SQL_*}}` tokens, Cloud SQL in bootstrap, `POSTGRES_*` config | the sidecar, `INSTANCE_CONNECTION_NAME` patches, SQL bootstrap steps, DB probe in readiness |
| **Schema migrations** | `k8s/base/migration-job.yaml`, `RUN_MIGRATIONS_ON_START` toggle in the entrypoint | the Job, the entrypoint migration block, `migrate` make targets |
| **Redis** | `k8s/base/redis.yaml`, `REDIS_HOST/PORT/DB` config, redis in compose + CI services | the redis manifests and all `REDIS_*` config |
| **Leader-elected background jobs** (scheduler) | single-process-per-pod CMD comment, Redis leader election, `SCHEDULER_ENABLED` | you may then run multiple uvicorn workers per pod |
| **HPA / PDB** | `hpa.yaml`, `pdb.yaml` at sync-wave 3 | both files |
| **Public ingress** | add an Ingress/Gateway + BackendConfig (not in the reference — it is ClusterIP + port-forward only) | keep `type: ClusterIP` |

**Redis: in-cluster vs Memorystore.** The reference started on Memorystore and moved to
an in-cluster `redis:7-alpine` Deployment (`k8s/base/redis.yaml`, `emptyDir`, no
persistence) specifically so the whole stack can scale to zero — Memorystore bills 24/7
and cannot be stopped. Use in-cluster Redis when Redis holds only rebuildable cache and
locks. Use Memorystore only when you need durability/HA, and then accept the always-on
cost and set `REDIS_HOST` to the instance's private IP (both must sit on the same VPC).

---

## 4. Make the app deployment-ready first

The manifests below assume these exist. Add them if they do not, in the smallest way that
fits the codebase's existing style.

### 4.1 Two distinct health endpoints — this distinction is not optional

- **`{{HEALTH_PATH}}` (liveness)** — **zero dependencies.** Returns 200 whenever the
  process is alive. It must NOT touch Postgres, Redis, or any network peer. Kubernetes
  restarts the pod when liveness fails; if liveness checked the DB, a brief DB blip would
  crash-loop every replica and turn a small outage into a total one.
- **`{{READY_PATH}}` (readiness)** — checks the dependencies the service needs to serve a
  request (Postgres `SELECT 1`, Redis `PING`). Returns **503** when any is down.
  Kubernetes then pulls that pod out of the Service endpoints without killing it, and it
  rejoins when the dependency recovers.

Also keep them unauthenticated: the Docker `HEALTHCHECK` and the kubelet probes call them
with no credentials. If you add an auth layer later, both paths must stay exempt.

### 4.2 Config comes from environment variables only

Every knob must be settable by env var, because in-cluster config arrives via `envFrom`
(ConfigMap + Secret). Use a single settings module (pydantic-settings in the reference).

**Make secrets required with no default.** In the reference, `config.py` has no default
for `POSTGRES_PASSWORD`, so a missing secret is a loud startup crash rather than a silent
connection failure hours later. Do the same for every credential.

Keep a committed `.env.example` that documents **every** variable, marks which are
secrets, and states that the real `.env` is git-ignored and never ships to the cluster.

### 4.3 Migrations must be idempotent and runnable as a one-shot command

The migration Job runs `{{MIGRATE_CMD}}` in the same image as the app, bypassing the
image ENTRYPOINT. The command must be safe to re-run (already-applied migrations are
skipped, tracked in a `schema_migrations`-style table) and must exit non-zero on failure
so the Job fails and the deploy stops.

### 4.4 One process per pod when a scheduler runs in-process

The reference runs a **single** uvicorn process per container and scales via replicas +
HPA, because APScheduler runs inside the app process and uses Redis leader election to
guarantee exactly one poller cluster-wide. Multiple workers per pod would each try to
elect. If this service has no in-process background work, multiple workers are fine —
but say so explicitly in the Dockerfile comment either way.

---

## 5. Container — `docker/Dockerfile` and `docker/entrypoint.sh`

Multi-stage, non-root, no build tooling or tests in the runtime image.

```dockerfile
# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder stage: create a venv and install dependencies (+ editable package)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Isolated venv we can copy wholesale into the runtime image
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install deps from pyproject. src/ is needed because the editable install
# resolves the declared packages from it, at the same path used at runtime.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

# ---------------------------------------------------------------------------
# Runtime stage: slim, non-root, no build tooling, no tests
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH={{PYTHONPATH}}

WORKDIR /app

# Non-root runtime user
RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

# Application code only — tests/ are intentionally NOT shipped to the image
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

# Make entrypoint executable and normalise CRLF (in case of a Windows checkout)
RUN chmod +x /app/docker/entrypoint.sh && \
    sed -i 's/\r$//' /app/docker/entrypoint.sh && \
    chown -R app:app /app

USER app

EXPOSE {{PORT}}

# Liveness only — hits the dependency-free {{HEALTH_PATH}} (DB/Redis issues won't
# fail it; k8s uses {{READY_PATH}} for readiness).
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{{PORT}}{{HEALTH_PATH}}')" || exit 1

# Runs migrations (unless RUN_MIGRATIONS_ON_START=false) before starting the app.
ENTRYPOINT ["/app/docker/entrypoint.sh"]

# Single uvicorn process per container. Scale horizontally via k8s replicas + HPA.
CMD ["uvicorn", "{{APP_MODULE}}", "--host", "0.0.0.0", "--port", "{{PORT}}"]
```

Notes that matter and are easy to lose:
- The `sed -i 's/\r$//'` line is **required** on Windows checkouts. Without it the
  entrypoint fails with a cryptic `exec format error` / `no such file or directory`.
- Adjust the `COPY` set to the directories this repo actually has. Never copy `tests/`,
  `.env`, or `.git`. Add a `.dockerignore` covering `.git`, `.venv`, `tests`, `.env*`,
  `__pycache__`, `*.pyc`, `.ruff_cache`, `.mypy_cache`, `k8s`, `docs`.
- If the repo uses uv/poetry, swap only the builder's install step; keep the venv-copy
  shape.

`docker/entrypoint.sh` — waits for the DB, optionally migrates, then `exec`s the CMD:

```bash
#!/bin/bash
set -e

echo "Starting application entrypoint..."

# Wait for PostgreSQL to be ready (with timeout)
echo "Waiting for PostgreSQL to be ready..."
timeout=60
while [ $timeout -gt 0 ]; do
    if python -c "
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path('/app/src')))
try:
    from db.connection import check_db_health
    sys.exit(0 if asyncio.run(check_db_health()) else 1)
except Exception as e:
    print(f'Health check error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        echo "PostgreSQL is ready!"
        break
    fi
    echo "Waiting for PostgreSQL... ($timeout seconds remaining)"
    sleep 1
    timeout=$((timeout-1))
done

if [ $timeout -eq 0 ]; then
    echo "ERROR: PostgreSQL health check timeout"
    exit 1
fi

# Default true so docker-compose / local dev behaviour is unchanged. In Kubernetes
# the app Deployment sets RUN_MIGRATIONS_ON_START=false and a dedicated migration
# Job owns the schema, so replicas never race each other.
RUN_MIGRATIONS_ON_START="${RUN_MIGRATIONS_ON_START:-true}"

if [ "$RUN_MIGRATIONS_ON_START" = "true" ]; then
    echo "Running database migrations..."
    python scripts/migrate_db.py || { echo "ERROR: migration failed"; exit 1; }
    echo "Migrations completed successfully. Starting application..."
else
    echo "RUN_MIGRATIONS_ON_START=$RUN_MIGRATIONS_ON_START — skipping migrations."
fi

exec "$@"
```

Replace the import in the health probe with this service's real DB-check function. Drop
the whole file (and the ENTRYPOINT line) if the service has no database.

---

## 6. `.github/workflows/ci.yml` — never touches the cluster

Runs on PRs into `main` and pushes to `main`. Three independent jobs.

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

# Cancel superseded runs on the same ref.
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    env:
      # config requires POSTGRES_PASSWORD at import time; provide it job-wide.
      PYTHONPATH: src
      POSTGRES_HOST: localhost
      POSTGRES_PORT: "5432"
      POSTGRES_DB: {{DB_NAME}}
      POSTGRES_USER: {{DB_USER}}
      POSTGRES_PASSWORD: ci-password
      REDIS_HOST: localhost
      REDIS_PORT: "6379"
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: {{DB_NAME}}
          POSTGRES_USER: {{DB_USER}}
          POSTGRES_PASSWORD: ci-password
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U {{DB_USER}} -d {{DB_NAME}}"
          --health-interval 10s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint (ruff)
        run: ruff check src/ tests/

      # Not yet blocking: the codebase is not fully typed. Drop continue-on-error
      # once `mypy src/` is clean.
      - name: Type check (mypy)
        continue-on-error: true
        run: mypy src/

      - name: Run migrations against the CI database
        run: python scripts/migrate_db.py

      - name: Tests (pytest)
        run: |
          set +e
          python -m pytest tests/ -v
          code=$?
          set -e
          # Exit code 5 = no tests collected (stubs only). Don't fail CI on it.
          if [ "$code" -eq 5 ]; then
            echo "::warning::pytest collected no tests yet — add real tests under tests/."
            exit 0
          fi
          exit "$code"

  build-image:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Build image (no push)
        uses: docker/build-push-action@v6
        with:
          context: .
          file: docker/Dockerfile
          push: false
          load: true
          tags: {{SERVICE}}:ci
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: Smoke test the image imports
        run: |
          docker run --rm -e POSTGRES_PASSWORD=ci \
            --entrypoint python {{SERVICE}}:ci \
            -c "{{IMPORT}}; print('image imports OK')"

  validate-manifests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install kustomize + kubeconform
        run: |
          curl -sSL https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh | bash
          sudo mv kustomize /usr/local/bin/
          curl -sSL https://github.com/yannh/kubeconform/releases/latest/download/kubeconform-linux-amd64.tar.gz | tar -xz kubeconform
          sudo mv kubeconform /usr/local/bin/
      - name: Validate overlays
        run: |
          for env in prod; do
            echo "== $env =="
            kustomize build "k8s/overlays/$env" \
              | kubeconform -strict -summary -ignore-missing-schemas -kubernetes-version 1.29.0
          done
```

Design points to preserve:
- **Ruff is the blocking gate; mypy is advisory** until the codebase is typed. Say so in a
  comment so nobody "fixes" it by deleting the step.
- **The image smoke test catches the failure Docker build alone misses**: a build can
  succeed while the app is unimportable inside the image (missing `PYTHONPATH`, a package
  not copied, a config var required at import time). That one `docker run` is worth more
  than it looks.
- **`kubeconform` on the rendered overlay** catches malformed manifests before ArgoCD
  ever sees them. `-ignore-missing-schemas` is needed for CRDs like ArgoCD's.
- Pin the ruff version to `{{RUFF_VERSION}}` everywhere (CI, pre-commit hook, make
  targets) so all three agree; a version drift means "clean locally, red in CI".

---

## 7. `.github/workflows/cd-prod.yml` — build, push, bump the tag

```yaml
name: CD Prod

# Build + push the image to Artifact Registry and bump the prod overlay's image
# tag (GitOps). ArgoCD then syncs the cluster from k8s/overlays/prod. No cluster
# credentials live in GitHub — CI only writes to Artifact Registry and to git.
#
# Required repo configuration:
#   Variables:  GCP_PROJECT_ID, GCP_REGION, AR_HOST, AR_REPO
#   Secrets:    GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_DEPLOY_SERVICE_ACCOUNT

on:
  push:
    branches: [main]

concurrency:
  group: cd-prod
  cancel-in-progress: false     # never cancel a half-finished deploy

permissions:
  contents: write      # commit the image-tag bump back to main
  id-token: write      # Workload Identity Federation (keyless auth to GCP)

jobs:
  build-push-bump:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to Google Cloud (WIF)
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_DEPLOY_SERVICE_ACCOUNT }}

      - name: Set up gcloud
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for Artifact Registry
        run: gcloud auth configure-docker "${{ vars.AR_HOST }}" --quiet

      - name: Compute image reference
        id: image
        run: |
          IMAGE="${{ vars.AR_HOST }}/${{ vars.GCP_PROJECT_ID }}/${{ vars.AR_REPO }}/{{SERVICE}}"
          echo "ref=${IMAGE}" >> "$GITHUB_OUTPUT"
          echo "tag=${GITHUB_SHA}" >> "$GITHUB_OUTPUT"

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: docker/Dockerfile
          push: true
          tags: |
            ${{ steps.image.outputs.ref }}:${{ steps.image.outputs.tag }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Install kustomize
        run: |
          curl -sSL https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh | bash
          sudo mv kustomize /usr/local/bin/

      - name: Bump prod overlay image tag
        run: |
          cd k8s/overlays/prod
          kustomize edit set image "{{SERVICE}}=${{ steps.image.outputs.ref }}:${{ steps.image.outputs.tag }}"

      - name: Commit tag bump (GitOps)
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          if git diff --quiet; then
            echo "No image change to commit."
            exit 0
          fi
          git add k8s/overlays/prod/kustomization.yaml
          # [skip ci] prevents this bot commit from retriggering CD on main.
          git commit -m "chore(prod): deploy {{SERVICE}} ${{ steps.image.outputs.tag }} [skip ci]"
          git push
```

Design points to preserve:
- **Tag by immutable git SHA**, never `:latest`. `a1b2c3d` always means exactly that
  source. This is what makes both rollback and "what is actually running?" trivial.
- **`[skip ci]` on the bot commit** — without it, the bump commit to `main` retriggers CD,
  which builds again, bumps again, and you have an infinite deploy loop.
- **`cancel-in-progress: false`** on the CD concurrency group. Cancelling a deploy midway
  can leave the image pushed but git un-bumped.
- **`permissions: contents: write` + `id-token: write`** are both required: the first to
  push the bump, the second for keyless WIF. No JSON key file anywhere.
- **The deploy commit is the deployment record.** `git log` on `main` reads as an audit
  trail of exactly when prod moved to which image.

---

## 8. `k8s/base/` — shared manifests

Create: `kustomization.yaml`, `serviceaccount.yaml`, `deployment.yaml`, `service.yaml`,
`redis.yaml`, `migration-job.yaml`, `hpa.yaml`, `pdb.yaml`, `secret.example.yaml`.

### 8.0 The sync-wave contract — get this right or syncs stall

ArgoCD orders resources by `argocd.argoproj.io/sync-wave`:

| Wave | Resource | Why |
|---|---|---|
| 0 (default) | ServiceAccount, ConfigMap, Service, Redis | dependencies of everything else |
| 1 | migration Job (Sync hook) | schema is ready before any new pod starts |
| 2 | Deployment | rolls only after migrations succeed |
| 3 | HPA, PDB | **an HPA with no scale target, or a PDB matching no pods, reports Degraded and stalls the whole sync** if created earlier |

### 8.1 `kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

# Base manifests for {{SERVICE}}. Environment-specific values (namespace, image
# tag, replicas, resources, Cloud SQL instance) live in overlays/. Do not deploy
# this base directly — deploy an overlay.

resources:
  - serviceaccount.yaml
  - deployment.yaml
  - service.yaml
  - redis.yaml
  - migration-job.yaml
  - hpa.yaml
  - pdb.yaml

labels:
  - pairs:
      app.kubernetes.io/name: {{SERVICE}}
      app.kubernetes.io/part-of: pae-microservices
    includeSelectors: true

# Non-secret configuration. Overlays override env-specific keys with a
# configMapGenerator using `behavior: merge`. The generated name gets a content
# hash suffix, so any config change rolls the Deployment automatically.
configMapGenerator:
  - name: {{CONFIGMAP}}
    literals:
      - LOG_LEVEL=INFO
      - API_HOST=0.0.0.0
      - API_PORT={{PORT}}
      # Redis runs in-cluster (see redis.yaml) — reached by its Service DNS name.
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      # Postgres via the Cloud SQL Auth Proxy sidecar on localhost
      - POSTGRES_HOST=127.0.0.1
      - POSTGRES_PORT=5432
      - POSTGRES_DB={{DB_NAME}}
      - POSTGRES_USER={{DB_USER}}
      # App pods do NOT migrate; the wave-1 migration Job owns the schema
      - RUN_MIGRATIONS_ON_START=false
      # --- {{APP_ENV}}: this service's own config keys go here ---

# Image name is a logical placeholder; overlays pin newName (Artifact Registry)
# and newTag (CD sets the git SHA via `kustomize edit set image`).
images:
  - name: {{SERVICE}}
    newTag: latest
```

Two things worth understanding:
- **`configMapGenerator` hashes its content into the generated name.** Change any config
  literal and the ConfigMap name changes, which changes the Deployment's pod spec, which
  triggers a rollout automatically. A hand-written ConfigMap would silently leave pods
  running stale config.
- **`labels ... includeSelectors: true` stamps `app.kubernetes.io/name` on *everything*** —
  including the redis and migrate pods. That is why the app Deployment/Service/PDB also
  carry the narrower `app: {{APP_LABEL}}` label (see below). Without it the Service load-
  balances API traffic onto redis pods.

### 8.2 `deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{SERVICE}}
  annotations:
    # Roll out only after the migration Job (wave 1) completes.
    argocd.argoproj.io/sync-wave: "2"
spec:
  # replicas is overridden per overlay.
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: {{SERVICE}}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0     # never drop below current capacity
      maxSurge: 1
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{SERVICE}}
        # Distinguishes app pods from redis/migrate pods (which share
        # app.kubernetes.io/name via the base labels transformer) so the app
        # Service targets only these pods.
        app: {{APP_LABEL}}
    spec:
      serviceAccountName: {{KSA}}
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        runAsGroup: 999
        fsGroup: 999
        seccompProfile:
          type: RuntimeDefault
      # Cloud SQL Auth Proxy as a native sidecar (starts before, terminates after
      # the app). Requires GKE >= 1.28 (Autopilot qualifies). App reaches Postgres
      # at 127.0.0.1:5432. INSTANCE_CONNECTION_NAME is patched per overlay.
      initContainers:
        - name: cloud-sql-proxy
          restartPolicy: Always          # <- this is what makes it a *native sidecar*
          image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.14.1
          args:
            - "--structured-logs"
            - "--port=5432"
            # Health-check server for the probes below. Must bind 0.0.0.0 (not the
            # default localhost) so the kubelet can reach it at the pod IP.
            - "--health-check"
            - "--http-address=0.0.0.0"
            - "--http-port=9801"
            - "$(INSTANCE_CONNECTION_NAME)"
          env:
            - name: INSTANCE_CONNECTION_NAME
              value: REPLACE_PROJECT:REGION:INSTANCE
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits:   { memory: 128Mi }
          startupProbe:
            httpGet: { path: /startup, port: 9801 }
            periodSeconds: 3
            failureThreshold: 20
          livenessProbe:
            httpGet: { path: /liveness, port: 9801 }
            periodSeconds: 10
      containers:
        - name: app
          image: {{SERVICE}}
          ports:
            - name: http
              containerPort: {{PORT}}
          envFrom:
            - configMapRef: { name: {{CONFIGMAP}} }
            - secretRef:    { name: {{SECRET}} }
          env:
            - name: POD_NAME
              valueFrom:
                fieldRef: { fieldPath: metadata.name }
          # Liveness: dependency-free, must not depend on DB/Redis.
          livenessProbe:
            httpGet: { path: {{HEALTH_PATH}}, port: http }
            initialDelaySeconds: 5
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3
          # Readiness: gates traffic on Postgres + Redis.
          readinessProbe:
            httpGet: { path: {{READY_PATH}}, port: http }
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          # Startup: give the process time to come up before liveness kicks in.
          startupProbe:
            httpGet: { path: {{HEALTH_PATH}}, port: http }
            periodSeconds: 5
            failureThreshold: 30
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          # resources are set per overlay.
          resources:
            requests: { cpu: 100m, memory: 256Mi }
            limits:   { memory: 512Mi }
```

- `restartPolicy: Always` on an initContainer is the **native sidecar** feature
  (k8s ≥1.28): it starts before the app and terminates after it, so the app never
  outlives its database tunnel. On an older cluster you would need the old
  `containers` + preStop-hook dance instead.
- The proxy's `--http-address=0.0.0.0` matters: the default binds localhost only and the
  kubelet's probe (which comes in on the pod IP) would fail.
- Set **memory limits but no CPU limit** (requests only). CPU limits cause throttling;
  memory is the one you actually want capped.

### 8.3 `service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{SERVICE}}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: {{SERVICE}}
    # Target only app pods, not the redis/migrate pods that share the name label.
    app: {{APP_LABEL}}
  ports:
    - name: http
      port: {{PORT}}
      targetPort: http
      protocol: TCP
```

`ClusterIP` is deliberate — nothing is exposed publicly; you reach it with
`kubectl port-forward`. Adding an Ingress is a separate, explicit decision.

### 8.4 `migration-job.yaml`

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{SERVICE}}-migrate
  annotations:
    # Run as an ArgoCD **Sync hook** at wave 1. Within the Sync phase ArgoCD orders
    # hooks and regular resources together by wave, so this still runs after wave-0
    # (ServiceAccount/ConfigMap) and before the wave-2 Deployment — its deps exist
    # and migrations finish before the app rolls.
    # Crucially, hooks are EXCLUDED from the app's sync-status diff: a completed Job
    # never shows OutOfSync, so selfHeal doesn't keep re-running it (no churn or
    # flapping). BeforeHookCreation deletes the previous Job and recreates it on each
    # real sync, which also sidesteps the immutable-Job-selector error without Force.
    argocd.argoproj.io/hook: Sync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
    argocd.argoproj.io/sync-wave: "1"
spec:
  backoffLimit: 3
  activeDeadlineSeconds: 600
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{SERVICE}}
        app.kubernetes.io/component: migrate
    spec:
      restartPolicy: Never
      serviceAccountName: {{KSA}}
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        runAsGroup: 999
        fsGroup: 999
        seccompProfile: { type: RuntimeDefault }
      initContainers:
        - name: cloud-sql-proxy
          restartPolicy: Always
          image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.14.1
          args: ["--structured-logs", "--port=5432", "$(INSTANCE_CONNECTION_NAME)"]
          env:
            - name: INSTANCE_CONNECTION_NAME
              value: REPLACE_PROJECT:REGION:INSTANCE
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits:   { memory: 128Mi }
      containers:
        - name: migrate
          image: {{SERVICE}}
          # Bypass the image ENTRYPOINT (which starts uvicorn) and just migrate.
          command: {{MIGRATE_CMD}}
          envFrom:
            - configMapRef: { name: {{CONFIGMAP}} }
            - secretRef:    { name: {{SECRET}} }
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 100m, memory: 256Mi }
            limits:   { memory: 512Mi }
```

**This annotation set is hard-won — do not "simplify" it.** An earlier iteration used a
plain (non-hook) Job with `Replace=true, Force=true`, which made ArgoCD's selfHeal
re-run migrations on every reconcile and flap the app's health forever. `hook: Sync` +
`BeforeHookCreation` fixes both the flapping and the "Job selector is immutable" error.

### 8.5 `redis.yaml` (in-cluster, ephemeral)

```yaml
# In-cluster Redis (cache + scheduler leader-election/job locks).
# Replaces Memorystore so the whole stack can scale to zero (no always-on managed
# Redis to pay for). Ephemeral on purpose — the cache is rebuildable and the
# scheduler simply re-elects a leader after a restart.
# Distinct `app: {{SERVICE}}-redis` label keeps the redis Service from matching app
# pods (the base labels transformer stamps app.kubernetes.io/name on everything).
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels: { app: {{SERVICE}}-redis }
  strategy: { type: Recreate }
  template:
    metadata:
      labels: { app: {{SERVICE}}-redis }
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: redis
          image: redis:7-alpine
          args: ["--save", "", "--appendonly", "no"]   # no persistence: cache/locks only
          ports:
            - name: redis
              containerPort: 6379
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits:   { memory: 256Mi }
          readinessProbe:
            exec: { command: ["redis-cli", "ping"] }
            periodSeconds: 10
            timeoutSeconds: 3
          livenessProbe:
            tcpSocket: { port: redis }
            periodSeconds: 15
          volumeMounts:
            - { name: data, mountPath: /data }
      volumes:
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  type: ClusterIP
  selector: { app: {{SERVICE}}-redis }
  ports:
    - { name: redis, port: 6379, targetPort: redis, protocol: TCP }
```

### 8.6 `hpa.yaml` / `pdb.yaml`

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{SERVICE}}
  annotations:
    # Created after the Deployment (wave 2) exists — an HPA with no scale target
    # reports Degraded, which would stall the sync if it ran in an earlier wave.
    argocd.argoproj.io/sync-wave: "3"
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: {{SERVICE}} }
  minReplicas: 2      # overridden per overlay
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 70 }
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{SERVICE}}
  annotations:
    argocd.argoproj.io/sync-wave: "3"
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: {{SERVICE}}
      app: {{APP_LABEL}}     # scope to app pods only
```

### 8.7 `serviceaccount.yaml` and `secret.example.yaml`

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{KSA}}
  # Workload Identity: bind this KSA to a GCP service account that has
  # roles/cloudsql.client (for the Cloud SQL Auth Proxy). The annotation value is
  # set per environment in the overlay (or by scripts/gcp_bootstrap.sh).
  annotations:
    iam.gke.io/gcp-service-account: REPLACE_GSA_EMAIL
```

```yaml
# TEMPLATE ONLY — do NOT commit real values and do NOT add this file to
# kustomization.yaml `resources`. The real Secret is created out-of-band from GCP
# Secret Manager so credentials never live in git.
#
#   kubectl -n {{NAMESPACE}} create secret generic {{SECRET}} \
#     --from-literal=POSTGRES_PASSWORD="$(gcloud secrets versions access latest --secret={{SM_DB_PASSWORD}})" \
#     --from-literal=REDIS_PASSWORD=""
#
# Future: replace with an ExternalSecret (External Secrets Operator) so the Secret
# is declarative and GitOps-managed.
apiVersion: v1
kind: Secret
metadata:
  name: {{SECRET}}
type: Opaque
stringData:
  POSTGRES_PASSWORD: REPLACE_ME
  REDIS_PASSWORD: ""
```

Keeping `secret.example.yaml` **out of the `resources:` list** is deliberate: it can never
be applied by accident.

---

## 9. `k8s/overlays/prod/kustomization.yaml` — the highest-density file

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: {{NAMESPACE}}

resources:
  - namespace.yaml
  - ../../base

# CD pins the tag to the built git SHA via:
#   kustomize edit set image {{SERVICE}}={{AR_IMAGE}}:<sha>
images:
  - name: {{SERVICE}}
    newName: {{AR_IMAGE}}
    newTag: latest        # CD rewrites this line on every deploy

replicas:
  - { name: {{SERVICE}}, count: 2 }

# Override env-specific, non-secret config. Merged onto the base ConfigMap; the
# resulting content hash rolls the Deployment when any value changes.
configMapGenerator:
  - name: {{CONFIGMAP}}
    behavior: merge
    literals:
      - LOG_LEVEL=INFO
      # --- prod values for {{APP_ENV}} ---

patches:
  # Cloud SQL instance + prod app resources.
  - target: { kind: Deployment, name: {{SERVICE}} }
    patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: {{SERVICE}}
      spec:
        template:
          spec:
            initContainers:
              - name: cloud-sql-proxy
                # Full args set explicitly here (not just in base) so the overlay
                # render is self-contained and robust to kustomize patch-merge quirks.
                args:
                  - "--structured-logs"
                  - "--port=5432"
                  - "--health-check"
                  - "--http-address=0.0.0.0"
                  - "--http-port=9801"
                  - "$(INSTANCE_CONNECTION_NAME)"
                env:
                  - name: INSTANCE_CONNECTION_NAME
                    value: {{SQL_CONN}}
            containers:
              - name: app
                resources:
                  requests: { cpu: 250m, memory: 512Mi }
                  limits:   { memory: 1Gi }
  # Cloud SQL instance for the migration Job.
  - target: { kind: Job, name: {{SERVICE}}-migrate }
    patch: |-
      apiVersion: batch/v1
      kind: Job
      metadata:
        name: {{SERVICE}}-migrate
      spec:
        template:
          spec:
            initContainers:
              - name: cloud-sql-proxy
                env:
                  - name: INSTANCE_CONNECTION_NAME
                    value: {{SQL_CONN}}
  # Workload Identity binding for prod.
  - target: { kind: ServiceAccount, name: {{KSA}} }
    patch: |-
      apiVersion: v1
      kind: ServiceAccount
      metadata:
        name: {{KSA}}
        annotations:
          iam.gke.io/gcp-service-account: {{GSA}}
  # Autoscaling range for prod.
  - target: { kind: HorizontalPodAutoscaler, name: {{SERVICE}} }
    patch: |-
      apiVersion: autoscaling/v2
      kind: HorizontalPodAutoscaler
      metadata:
        name: {{SERVICE}}
      spec:
        minReplicas: 2
        maxReplicas: 6
```

Plus `k8s/overlays/prod/namespace.yaml` declaring the namespace.

Two warnings from experience:
- `INSTANCE_CONNECTION_NAME` must be patched in **two** places (Deployment and Job).
  Forgetting the Job means migrations fail while the app is fine — a confusing half-deploy.
- `kustomize edit set image` **rewrites and reflows this file** (it strips/moves comments
  and reorders keys). Do not rely on comment placement inside `images:` surviving CD.

**Environments:** start with `prod` only. A second environment is a new overlay + a copy
of `cd-prod.yml` + *real GCP resources*. A dev overlay with unfilled `REPLACE_*` values
and an ArgoCD Application pointing at a placeholder repoURL is worse than nothing — the
reference repo deleted exactly such a scaffold because it never synced and only misled.

---

## 10. `k8s/argocd/application-prod.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{SERVICE}}-prod
  namespace: argocd
  # Keep the app from being pruned if the Application manifest is removed by mistake.
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/{{GH_REPO}}.git
    targetRevision: main
    path: k8s/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: {{NAMESPACE}}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
    retry:
      limit: 5
      backoff: { duration: 10s, factor: 2, maxDuration: 3m }
```

`selfHeal: true` means hand-edits to the cluster get reverted — git always wins. Whenever
you break-glass with `kubectl`, you must follow up by making git say the same thing.

---

## 11. Local dev + tooling parity

Provide the same local experience the reference has, because CI reproducibility depends on it.

**`docker-compose.yaml`** — app + postgres + redis, with **remapped host ports** so this
service doesn't collide with other services on the same laptop (the reference uses
`5435→5432` and `6380→6379`; pick unique ones and **document them**, since a local `.env`
must target the remapped ports). Use healthchecks + `depends_on: condition: service_healthy`.

**`Makefile`** (+ a `make.ps1` PowerShell wrapper if the team is on Windows) with at least:
`network`, `up`, `up-build`, `down`, `logs`, `shell`, `ps`, `test`, `lint`, `lint-fix`,
`format`, `migrate`, `run`, `cloud-down`, `cloud-up`.

Run lint in Docker so no local Python is required, and pin the same ruff version as CI:

```makefile
lint:
	docker run --rm -v "$(CURDIR):/io" ghcr.io/astral-sh/ruff:{{RUFF_VERSION}} check src/ tests/

lint-fix:
	docker run --rm -v "$(CURDIR):/io" ghcr.io/astral-sh/ruff:{{RUFF_VERSION}} check --fix src/ tests/
```

**Cost control — `cloud-down` / `cloud-up`.** GKE + Cloud SQL bill 24/7. Two targets
toggle everything (data preserved; idle cost ≈ Cloud SQL storage only):

```makefile
GCP_PROJECT  ?= {{GCP_PROJECT}}
GCP_REGION   ?= {{REGION}}
SQL_INSTANCE ?= {{SQL_INSTANCE}}
K8S_NS       ?= {{NAMESPACE}}

cloud-down:
	@kubectl -n argocd scale statefulset --all --replicas=0     # ArgoCD first, or it scales things back up
	@kubectl -n argocd scale deploy --all --replicas=0
	@kubectl -n $(K8S_NS) delete hpa {{SERVICE}} --ignore-not-found   # HPA would force min replicas
	@kubectl -n $(K8S_NS) scale deploy {{SERVICE}} redis --replicas=0
	@gcloud sql instances patch $(SQL_INSTANCE) --project=$(GCP_PROJECT) --activation-policy=NEVER --quiet

cloud-up:
	@gcloud sql instances patch $(SQL_INSTANCE) --project=$(GCP_PROJECT) --activation-policy=ALWAYS --quiet
	@until [ "$$(gcloud sql instances describe $(SQL_INSTANCE) --project=$(GCP_PROJECT) --format='value(state)')" = "RUNNABLE" ]; do sleep 10; done
	@kubectl -n argocd scale statefulset --all --replicas=1
	@kubectl -n argocd scale deploy --all --replicas=1
	@kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=180s
	@kubectl -n $(K8S_NS) scale deploy redis --replicas=1
	@kubectl -n $(K8S_NS) rollout status deploy/redis --timeout=120s
	@kubectl -n $(K8S_NS) scale deploy {{SERVICE}} --replicas=2
	@kubectl -n $(K8S_NS) rollout status deploy/{{SERVICE}} --timeout=240s
	@kubectl -n argocd annotate application {{SERVICE}}-prod argocd.argoproj.io/refresh=hard --overwrite
```

The **order in `cloud-down` is load-bearing**: scale ArgoCD to zero *first*, or its
selfHeal immediately restores the replicas you just scaled down; and delete the HPA, or it
forces `minReplicas` back up.

*Windows note:* GNU make's recipe shell often lacks `gke-gcloud-auth-plugin` even when
PowerShell has it, so these targets fail with "plugin not found". The reference solves it
by having the Makefile delegate to `make.ps1` on Windows, keeping one source of truth:

```makefile
ifeq ($(OS),Windows_NT)
cloud-down:
	@powershell -NoProfile -ExecutionPolicy Bypass -File make.ps1 cloud-down
else
# ... the real recipe ...
endif
```

**`.githooks/pre-commit`** — runs ruff in Docker on staged `.py` files only, skips
cleanly when Docker is absent, and prints the fix/bypass commands on failure. Activated
per clone with `git config core.hooksPath .githooks`.

---

## 12. `scripts/gcp_bootstrap.sh` — one-time infrastructure

A documented, reviewable shell script (a readable alternative to Terraform, to be replaced
by Terraform once the shape is stable). Idempotent-ish via `|| true`. Steps, in order:

1. `gcloud config set project`; enable APIs: `container`, `artifactregistry`, `sqladmin`,
   `secretmanager`, `redis`, `iamcredentials`, `sts`.
2. Artifact Registry docker repo `{{AR_REPO}}` in `{{REGION}}`.
3. GKE **Autopilot** cluster `{{CLUSTER}}` (Workload Identity on by default).
4. Cloud SQL Postgres 16 `{{SQL_INSTANCE}}` + database + user with a generated password.
   **`--edition=ENTERPRISE` is required** — without it Cloud SQL defaults to Enterprise
   Plus, which rejects custom tiers like `db-custom-1-3840`.
   Print `connectionName` → this is `{{SQL_CONN}}`.
5. *(Only if using Memorystore instead of in-cluster Redis)* create the instance on
   `--network=default` — the same VPC as the cluster — and print its private IP.
6. Secret Manager: store the DB password as `{{SM_DB_PASSWORD}}`.
7. **Cloud SQL proxy identity:** create `{{GSA}}`, grant `roles/cloudsql.client`, and bind
   `roles/iam.workloadIdentityUser` to
   `serviceAccount:{{GCP_PROJECT}}.svc.id.goog[{{NAMESPACE}}/{{KSA}}]`.
8. **GitHub deployer via WIF (keyless):** create `{{DEPLOYER_GSA}}`, grant
   `roles/artifactregistry.writer`, create the `github` workload-identity pool and an OIDC
   provider with
   `--attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"`,
   `--attribute-condition="assertion.repository=='{{GH_REPO}}'"`,
   `--issuer-uri="https://token.actions.githubusercontent.com"`, then bind
   `principalSet://iam.googleapis.com/${POOL}/attribute.repository/{{GH_REPO}}` to the SA.
9. **Print a summary block** with the exact GitHub Variables/Secrets to set and the exact
   overlay placeholders to fill. That printed block is what makes the script usable.

The **attribute condition is the security boundary** — it is what stops any other GitHub
repo from minting tokens for your project. Never omit it.

**GitHub configuration (do in the browser):**
- Variables: `GCP_PROJECT_ID`, `GCP_REGION`, `AR_HOST`, `AR_REPO`
- Secrets: `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`
- Branch ruleset on `main`: always enable **block force pushes** and **restrict
  deletions**. ⚠️ If you also enable **require a PR** or **require status checks**, you
  block CD's own tag-bump push to `main` and prod deploys silently stop. Fix by one of:
  add the GitHub Actions bot to the ruleset **bypass list** (simplest), have CD open a PR
  for the bump instead of pushing, or move tag updates to ArgoCD Image Updater. Note the
  `[skip ci]` bump commit runs no checks, so a status-check rule has nothing to evaluate
  on it — the bypass list is what lets it through.

**Cluster bootstrap (once):**
```bash
gcloud container clusters get-credentials {{CLUSTER}} --region {{REGION}}
kubectl create namespace {{NAMESPACE}}
kubectl -n {{NAMESPACE}} create secret generic {{SECRET}} \
  --from-literal=POSTGRES_PASSWORD="$(gcloud secrets versions access latest --secret={{SM_DB_PASSWORD}})" \
  --from-literal=REDIS_PASSWORD=""
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f k8s/argocd/application-prod.yaml     # run from the repo root
```
If the repo is **private**, connect it in ArgoCD (Settings → Repositories → CONNECT REPO
via HTTPS, with a fine-grained GitHub token scoped to *Contents: Read-only*) **before**
applying the Application, or it shows `ComparisonError: repository not accessible`.

---

## 13. Documentation to write

Three files, each with a different job. Do not merge them.

1. **`docs/DEPLOYMENT.md`** — the short reference: architecture diagram, manifest layout,
   the one-time setup summary, the CI/CD description, probe paths, environments, and the
   filled-in parameter table from §2.
2. **`docs/RUNBOOK.md`** — the teaching version, no SRE experience assumed. Include:
   a **cheatsheet** of the commands actually reached for; a **glossary** defining every
   term (image, registry, tag, overlay, sidecar, hook, reconcile, WIF, HPA, PDB…); the
   artifact chain (image → registry, tag → git, cluster reads both); **deploy = commit,
   rollback = commit**; where each secret lives; who creates what (human once vs.
   automation forever); and procedures grouped **by how often you do them** — install
   tools, GCP setup, GitHub setup, cluster bootstrap, daily deploy, daily local dev,
   rollback, password rotation, port-forward access, cost control.
3. **`docs/PER-SERVICE-CHANGES.md`** — the file-by-file map of what changes for the *next*
   service (this document's §2/§3, made concrete), so the framework keeps propagating.

Also update the repo `CLAUDE.md` with the new commands, the CI-blocking lint gate, and any
gotchas discovered along the way.

**Rollback, documented precisely** — the naive version is wrong and worth spelling out:
CD rebuilds on *every* push to `main`, so reverting the deploy commit just rebuilds the
latest code. The real options are:
- **Fast:** edit `newTag:` in `k8s/overlays/prod/kustomization.yaml` to a known-good SHA,
  commit with `[skip ci]`, push. ArgoCD deploys the old image (still in the registry).
- **Proper:** `git revert <sha-of-bad-merge>` through a PR; the pipeline rebuilds clean.
- **Emergency:** ArgoCD UI → History and Rollback — but **pause auto-sync first**, or it
  immediately syncs forward again. Then reconcile git with reality.

---

## 14. Verification — actually run these, then report what passed

Local, no cloud required:

```bash
# 1. Image builds and the app is importable *inside* the image
docker build -f docker/Dockerfile -t {{SERVICE}}:verify .
docker run --rm -e POSTGRES_PASSWORD=x --entrypoint python {{SERVICE}}:verify -c "{{IMPORT}}; print('ok')"

# 2. Manifests render and validate
kustomize build k8s/overlays/prod > /tmp/rendered.yaml
kubeconform -strict -summary -ignore-missing-schemas -kubernetes-version 1.29.0 /tmp/rendered.yaml

# 3. Sanity-grep the render for the things that break silently
grep -n "REPLACE_" /tmp/rendered.yaml        # must return NOTHING
grep -n "image:"   /tmp/rendered.yaml        # image path + tag as expected
grep -n "sync-wave" /tmp/rendered.yaml       # Job=1, Deployment=2, HPA/PDB=3
grep -n "INSTANCE_CONNECTION_NAME" -A1 /tmp/rendered.yaml   # set in BOTH Deployment and Job

# 4. Lint + tests exactly as CI runs them
docker run --rm -v "$PWD:/io" ghcr.io/astral-sh/ruff:{{RUFF_VERSION}} check src/ tests/
PYTHONPATH=src pytest tests/ -v

# 5. The whole stack locally
make up-build && curl -fsS http://localhost:{{PORT}}{{HEALTH_PATH}} && curl -fsS http://localhost:{{PORT}}{{READY_PATH}}

# 6. Workflow syntax (if `act` or `actionlint` is available)
actionlint .github/workflows/*.yml
```

In-cluster, after bootstrap:

```bash
kubectl -n {{NAMESPACE}} get pods                     # app pods Running, ALL containers ready
kubectl -n argocd get applications                    # expect Synced + Healthy
kubectl -n {{NAMESPACE}} logs job/{{SERVICE}}-migrate # migrations succeeded
kubectl -n {{NAMESPACE}} port-forward svc/{{SERVICE}} {{PORT}}:{{PORT}}
curl http://localhost:{{PORT}}{{READY_PATH}}
kubectl -n {{NAMESPACE}} get deploy {{SERVICE}} -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
#   ^ must equal newTag in k8s/overlays/prod/kustomization.yaml
```

---

## 15. The gotchas — every one of these cost real debugging time

**Container / build**
1. Windows CRLF line endings break `entrypoint.sh` — `sed -i 's/\r$//'` in the Dockerfile.
2. A green `docker build` does not mean the app imports. Keep the CI smoke-test `docker run`.
3. Flat-module layouts need `PYTHONPATH=/app/src` in the image *and* `PYTHONPATH=src` in CI.
4. Config that requires a secret at *import* time means CI must set a dummy value job-wide.

**CI/CD**
5. Omitting `[skip ci]` on the bump commit → infinite build/deploy loop.
6. `permissions: contents: write` **and** `id-token: write` are both mandatory in CD.
7. Branch protection on `main` blocks CD's push — bypass list, or CD opens a PR.
8. Pin ruff to the same version in CI, the pre-commit hook, and the make targets.
9. `kubeconform` needs `-ignore-missing-schemas` for CRDs.
10. pytest exit code 5 (no tests collected) fails CI unless special-cased.

**Kubernetes / ArgoCD**
11. A Kustomize `labels ... includeSelectors: true` stamps the name label on redis and
    migrate pods too — hence the narrower `app: {{APP_LABEL}}` on the Service/PDB selector.
12. HPA or PDB in an early sync wave reports Degraded and stalls the sync → wave 3.
13. A non-hook migration Job with `Replace/Force` flaps forever under selfHeal → use
    `hook: Sync` + `hook-delete-policy: BeforeHookCreation` + wave 1.
14. Job selectors are immutable; recreating without `BeforeHookCreation` errors out.
15. `INSTANCE_CONNECTION_NAME` must be patched in **both** the Deployment and the Job.
16. The Cloud SQL proxy's health server defaults to localhost — pass `--http-address=0.0.0.0`
    or the kubelet probe fails.
17. Native sidecars (`initContainers` + `restartPolicy: Always`) need GKE ≥ 1.28.
18. Liveness must never check the DB, or one DB blip crash-loops every replica.
19. `selfHeal: true` reverts hand-edits — always finish by making git match reality.
20. Private repo → connect it in ArgoCD before applying the Application.

**GCP**
21. Cloud SQL `--edition=ENTERPRISE` is required for custom tiers like `db-custom-1-3840`.
22. Set the project **ID**, not the project number, or gcloud errors out.
23. Memorystore and the cluster must share a VPC (`--network=default`) for the private IP
    to be reachable.
24. Billing must be linked before GKE/Cloud SQL/Memorystore can be created.
25. The WIF `--attribute-condition` pinning `assertion.repository` is the security
    boundary — never omit it.
26. In `cloud-down`, scale ArgoCD to zero *first* and delete the HPA, or nothing stays down.
27. On Windows, GNU make's shell may not see `gke-gcloud-auth-plugin` — delegate to
    PowerShell.

**Secrets**
28. Secrets never go in git. `secret.example.yaml` stays out of `resources:` on purpose.
29. Rotating the DB password takes four steps: Cloud SQL user → new Secret Manager version
    → recreate the k8s Secret → `kubectl rollout restart` (pods do not pick it up alone).

---

## 16. Deliverables checklist — report status honestly

```
docker/Dockerfile                        multi-stage, non-root, HEALTHCHECK, CRLF fix
docker/entrypoint.sh                     DB wait + RUN_MIGRATIONS_ON_START toggle
.dockerignore
.github/workflows/ci.yml                 lint-and-test | build-image | validate-manifests
.github/workflows/cd-prod.yml            WIF → build/push :<sha> → kustomize edit → commit [skip ci]
k8s/base/kustomization.yaml              configMapGenerator, labels, images placeholder
k8s/base/serviceaccount.yaml             WIF annotation
k8s/base/deployment.yaml                 wave 2, proxy sidecar, 3 probes, securityContext
k8s/base/service.yaml                    ClusterIP, narrow selector
k8s/base/redis.yaml                      (if Redis) in-cluster, ephemeral
k8s/base/migration-job.yaml              (if migrations) Sync hook, BeforeHookCreation, wave 1
k8s/base/hpa.yaml, pdb.yaml              wave 3
k8s/base/secret.example.yaml             template, NOT in resources:
k8s/overlays/prod/{kustomization,namespace}.yaml
k8s/argocd/application-prod.yaml         automated sync, prune, selfHeal
scripts/gcp_bootstrap.sh                 APIs, AR, GKE, Cloud SQL, SM, WIF ×2, printed summary
docker-compose.yaml                      app + deps, remapped host ports, healthchecks
Makefile (+ make.ps1)                    dev targets + lint + cloud-down/cloud-up
.githooks/pre-commit                     ruff in Docker on staged .py
.env.example                             every variable, secrets marked
docs/DEPLOYMENT.md                       reference + parameter table
docs/RUNBOOK.md                          teaching version: glossary, procedures, rollback
docs/PER-SERVICE-CHANGES.md              what changes for the next service
CLAUDE.md                                updated commands + gotchas
```

**Final report format.** For each item: created / skipped-and-why. Then, separately:
- Commands you **actually ran** and their real output (build, kustomize, kubeconform,
  ruff, pytest, compose).
- What you could **not** verify and why (no Docker, no gcloud auth, no cluster) — stated
  plainly, not glossed over.
- Every value the user must still fill in by hand, as a checklist.
- Open questions or decisions you made under assumption.

=== PROMPT ENDS HERE ===
