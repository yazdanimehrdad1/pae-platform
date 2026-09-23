# Deployment — pae-backend-ot

How this service is built, shipped, and run on GKE. For local dev see the repo
README / `docker-compose.yaml`.

## Overview

```
GitHub push ──► CI (lint, test, build, kubeconform)
main push  ──► CD (build+push image to Artifact Registry, bump prod overlay tag, commit)
                                   │
                                   ▼
                         ArgoCD watches k8s/overlays/prod ──► syncs GKE
```

- **Image**: multi-stage, non-root, single uvicorn process per pod. Scale via
  replicas + HPA (the scheduler uses Redis leader election, so exactly one pod
  polls regardless of replica count).
- **Data**: Cloud SQL (Postgres 16) reached through a Cloud SQL Auth Proxy
  **native sidecar** at `127.0.0.1:5432`; Redis runs **in-cluster** (`k8s/base/redis.yaml`),
  not on Memorystore.
  The app needs plain Postgres — no TimescaleDB extension is required.
- **Migrations**: run once per sync by a `PreSync` Job (`scripts/migrate_db.py`),
  never by app replicas (`RUN_MIGRATIONS_ON_START=false` in-cluster).
- **Config/secrets**: non-secret env in a ConfigMap (per-overlay); the two
  secrets (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`) in a k8s Secret sourced from
  GCP Secret Manager. See [`.env.example`](../.env.example).

## Manifests (Kustomize)

```
k8s/base/                 Deployment, Service, ConfigMap(gen), Job, HPA, PDB, SA
k8s/overlays/prod|dev/    namespace, image, replicas, resources, Cloud SQL/Redis, WIF
k8s/argocd/               ArgoCD Application per environment
```

Render locally:

```bash
kubectl kustomize k8s/overlays/prod
```

## One-time GCP setup

1. Run the bootstrap (provisions Artifact Registry, GKE Autopilot, Cloud SQL,
   Memorystore, Secret Manager, and Workload Identity Federation):

   ```bash
   PROJECT_ID=my-proj GITHUB_REPO=my-org/pae-backend-ot \
     bash scripts/gcp_bootstrap.sh
   ```

   It prints the GitHub Variables/Secrets and the overlay placeholder values to
   fill in. Prefer Terraform to codify this once the shape is stable.

2. Replace the `REPLACE_*` placeholders in `k8s/overlays/prod/kustomization.yaml`
   (image `newName`, `INSTANCE_CONNECTION_NAME`, `REDIS_HOST`, SA project) and in
   `k8s/argocd/application-prod.yaml` (`repoURL`).

3. Create the app Secret from Secret Manager:

   ```bash
   kubectl create namespace pae-backend-ot-prod
   kubectl -n pae-backend-ot-prod create secret generic pae-backend-ot-secrets \
     --from-literal=POSTGRES_PASSWORD="$(gcloud secrets versions access latest --secret=pae-backend-ot-postgres-password)" \
     --from-literal=REDIS_PASSWORD=""
   ```

   (Future: replace with an `ExternalSecret` so this is declarative/GitOps.)

4. Set the GitHub **Variables** (`GCP_PROJECT_ID`, `GCP_REGION`, `AR_HOST`,
   `AR_REPO`) and **Secrets** (`GCP_WORKLOAD_IDENTITY_PROVIDER`,
   `GCP_DEPLOY_SERVICE_ACCOUNT`) printed by the bootstrap.

## Deploy path

### GitOps with ArgoCD (target)

```bash
# once per cluster
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f k8s/argocd/application-prod.yaml
```

From then on: push to `main` → CD builds/pushes the image and commits the tag
bump → ArgoCD syncs (runs the PreSync migration Job, then rolls the Deployment).

### Bootstrap fallback (before ArgoCD is installed)

The overlays are directly appliable:

```bash
gcloud container clusters get-credentials pae-autopilot --region us-central1
kubectl apply -k k8s/overlays/prod
```

## CI/CD

- **`.github/workflows/ci.yml`** — on PRs targeting `main` and pushes to `main`:
  ruff, mypy (non-blocking until types are clean), migrations + pytest against
  service containers, docker build, and `kubeconform` on the prod overlay.
- **`.github/workflows/cd-prod.yml`** — on push to `main`: WIF auth → build+push
  `:<git-sha>` to Artifact Registry → `kustomize edit set image` in
  `overlays/prod` → commit `[skip ci]`.

Images are tagged by immutable git SHA. The bot commit carries `[skip ci]` so it
does not retrigger CD.

## Health & probes

- Liveness: `GET /api/healthz` (no dependencies).
- Readiness: `GET /api/readyz` (Postgres `SELECT 1` + Redis PING; 503 if either
  is down).

## Environments

`prod` is the only environment. `main` is the only long-lived branch: work on a
short-lived `feat/*` branch, open a PR into `main`, and merging deploys to prod.

There is no staging/dev environment. A scaffolded one (`dev` branch,
`k8s/overlays/dev`, `cd-dev.yml`, `application-dev.yaml`) was removed because it
was never wired up — its ArgoCD Application still held a placeholder `repoURL`
and the overlay had unfilled `REPLACE_*` values for Cloud SQL, Memorystore, and
the aggregator host, so nothing ever synced it. To add one later, copy the prod
overlay and `cd-prod.yml`, then stand up the matching GCP resources.
