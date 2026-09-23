# pae-backend-ot — Deployment Runbook

A beginner-friendly guide to how this service is built, shipped, and run. No SRE
experience assumed. If a term is new, check the **[Glossary](#2-glossary)** first.

> **DEPLOYMENT.md** is the short reference. **This file** is the teaching version:
> it explains *why*, defines every term, and gives copy-paste steps grouped by how
> often you do them.

---

## Table of contents

0. [**Cheatsheet — the commands you actually reach for**](#0-cheatsheet)
1. [The big picture (read this first)](#1-the-big-picture)
2. [Glossary — every term and its job](#2-glossary)
3. [The artifact chain — what actually flows](#3-the-artifact-chain)
4. [Deploy = a git commit. Rollback = a commit too.](#4-deploy--commit)
5. [Where credentials & secrets live](#5-secrets)
5b. [Who creates what — humans (once) vs. automation (forever)](#5b-who)
6. [Procedures — grouped by how often you do them](#6-procedures)
   - [6.0 Step 0 — install your tools (once per laptop)](#60-tools)
   - [6.0b Before the cloud setup — GCP account, project, billing, permissions](#60-account)
   - [6.A One-time setup — GCP & GKE infrastructure](#6a-gcp)
   - [6.B One-time setup — GitHub configuration](#6b-github)
   - [6.C One-time setup — bootstrap the cluster](#6c-cluster)
   - [6.D DAILY — deploy to PROD](#6d-prod)
   - [6.E DAILY — work on a feature](#6e-feature)
   - [6.F DAILY — run locally (no cloud)](#6f-local)
   - [6.G WHEN THINGS BREAK — rollback & emergencies](#6g-rollback)
   - [6.H OCCASIONAL — rotate the DB password](#6h-rotate)
   - [6.I ACCESS — reach the ArgoCD UI and the app (port-forward)](#6i-access)
   - [6.J COST CONTROL — stop/start all billable cloud resources](#6j-cost)
7. [Quick reference — names, values, files](#7-quickref)

---

<a name="0-cheatsheet"></a>
## 0. Cheatsheet — the commands you actually reach for

Everything here is explained in depth later; this is the copy-paste layer. Cluster
commands assume `kubectl` already points at the prod cluster (see **Context** below).

**Constants:** project `prd-pae-backend-ot` · cluster `pae-autopilot` · region
`us-central1` · namespace `pae-backend-ot-prod` · app container `app` · sidecar
`cloud-sql-proxy`

### Context — what am I pointed at?

Always check this first. Most "it doesn't work" moments are a wrong context or project.

```bash
gcloud config get-value project                 # current GCP project
kubectl config current-context                  # current cluster
kubectl config get-contexts                     # all clusters you can switch to
kubectl cluster-info                            # is the connection actually alive?
```

Set / fix them:

```bash
gcloud config set project prd-pae-backend-ot
gcloud container clusters get-credentials pae-autopilot \
  --region us-central1 --project prd-pae-backend-ot

kubectl config use-context gke_prd-pae-backend-ot_us-central1_pae-autopilot
kubectl config set-context --current --namespace=pae-backend-ot-prod   # stop typing -n
```

With that last line set, every `-n pae-backend-ot-prod` below becomes optional.

### Port-forward — reaching anything in the cluster

Both the app and ArgoCD are **ClusterIP** (cluster-internal), so nothing on your
machine can reach them until you open a tunnel. **`port-forward` blocks** — it must
keep running in its own terminal while you use another one.

| Target | Command | Then open |
|---|---|---|
| App API | `kubectl -n pae-backend-ot-prod port-forward svc/pae-backend-ot 8000:8000` | `http://localhost:8000` |
| ArgoCD UI | `kubectl -n argocd port-forward svc/argocd-server 8080:443` | `https://localhost:8080` (user `admin`) |
| Redis | `kubectl -n pae-backend-ot-prod port-forward svc/redis 6379:6379` | `redis-cli -p 6379` |

ArgoCD admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```
```powershell
[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String((kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}")))
```

**When port-forward misbehaves:**
- `Couldn't connect to server` on curl → the tunnel isn't running (closed terminal,
  Ctrl+C, or Cloud Shell timed out after ~20 min idle). Restart it.
- `address already in use` → pick another local port: `18000:8000`, then curl `:18000`.
- `no pods found` / `unable to forward` → nothing is running. See **Is it alive?**;
  you may have run `cloud-down`.
- Locally, port 8000 may already be taken by another project. Use `18000:8000`.

### Curl the API (with a forward running)

```bash
curl http://localhost:8000/api/healthz      # liveness — no dependencies, always 200 if up
curl http://localhost:8000/api/readyz       # readiness — 503 if Postgres or Redis is down
curl http://localhost:8000/api/db_health    # Postgres only
curl http://localhost:8000/api/redis_health # Redis only
curl http://localhost:8000/api/health_modbus_client
```

Browse `http://localhost:8000/docs` for the interactive Swagger UI — the easiest way
to see every endpoint and try one without hand-writing the curl.

`readyz` returning 503 is a **real failure**, not a tunnel problem — go read the logs.

Common data endpoints (all prefixed `/api`):

```bash
curl http://localhost:8000/api/sites
curl http://localhost:8000/api/devices/site/{site_id}/devices
curl http://localhost:8000/api/device-points/site/{site_id}/device/{device_id}
curl http://localhost:8000/api/device-point-readings/site/{site_id}/device/{device_id}/latest
curl "http://localhost:8000/api/device-point-readings/timeseries/site/{site_id}/device/{device_id}?start=2026-01-01T00:00:00Z&end=2026-01-02T00:00:00Z"
curl http://localhost:8000/api/cache/health
curl http://localhost:8000/api/cache/keys
```

> A global middleware validates `start`/`end` on every request — a malformed time
> range gets rejected before your handler ever runs.

### Is it alive? — pods, logs, events

```bash
kubectl -n pae-backend-ot-prod get pods                    # expect pae-backend-ot-... Running, all containers ready
kubectl -n pae-backend-ot-prod get all                     # pods, svc, deploy, hpa at a glance
kubectl -n pae-backend-ot-prod rollout status deploy/pae-backend-ot

kubectl -n pae-backend-ot-prod logs deploy/pae-backend-ot -c app --tail=100
kubectl -n pae-backend-ot-prod logs deploy/pae-backend-ot -c app -f          # follow
kubectl -n pae-backend-ot-prod logs deploy/pae-backend-ot -c app --previous  # last crash
kubectl -n pae-backend-ot-prod logs -l app.kubernetes.io/name=pae-backend-ot -c app --tail=50

kubectl -n pae-backend-ot-prod describe pod <pod-name>     # why a pod won't start
kubectl -n pae-backend-ot-prod get events --sort-by=.lastTimestamp | tail -20
```

`-c app` matters — the pod also runs the `cloud-sql-proxy` sidecar, and without the
flag you may get the proxy's logs instead of the app's.

Migrations and a shell inside the pod:

```bash
kubectl -n pae-backend-ot-prod get jobs                              # migration Job status
kubectl -n pae-backend-ot-prod logs job/pae-backend-ot-migrate      # why a migration failed
kubectl -n pae-backend-ot-prod exec -it deploy/pae-backend-ot -c app -- /bin/sh
kubectl -n pae-backend-ot-prod rollout restart deploy/pae-backend-ot
```

### ArgoCD — what does git say should be running?

```bash
kubectl -n argocd get applications                  # SYNC STATUS / HEALTH STATUS
kubectl -n argocd describe application pae-backend-ot-prod
kubectl -n argocd logs deploy/argocd-application-controller --tail=50
```

Healthy = `Synced` + `Healthy`. `OutOfSync` means the cluster hasn't caught up with
git yet (wait, or hit **Sync** in the UI). `Progressing` right after a deploy is
normal for ~1 min while the HPA collects metrics.

### Cost control — the cluster bills 24/7

```bash
make cloud-down     # or .\make.ps1 cloud-down — scales app+redis+argocd to 0, stops Cloud SQL
make cloud-up       # or .\make.ps1 cloud-up   — brings it all back (~2–3 min)
```

If `get pods` shows `No resources found`, you're almost certainly still scaled down.
Data survives `cloud-down` — Cloud SQL is stopped, not deleted. Full detail in **6.J**.

### Local development (no cloud at all)

```powershell
docker network create pae-shared-network    # once per machine
.\make.ps1 up-build                         # build + start postgres, redis, app
.\make.ps1 logs                             # tail container logs
.\make.ps1 down                             # stop

.\make.ps1 test                             # pytest (start postgres too for integration tests)
.\make.ps1 lint                             # ruff + mypy — CI fails on ruff errors
.\make.ps1 lint-fix                         # auto-fix imports/typing/whitespace
.\make.ps1 format                           # black + ruff
```

Health locally (note: `.\make.ps1 health` targets a dead URL — use this instead):

```powershell
Invoke-WebRequest http://localhost:8000/api/healthz | Select-Object -Expand Content
```

Host ports are remapped: app **8000**, postgres **5435**→5432, redis **6380**→6379.
A local `.env` must target 5435/6380.

### Ship a change

```bash
git checkout main && git pull origin main
git checkout -b feat/short-name
# ...edit, commit...
git push -u origin feat/short-name
gh pr create --base main          # CI runs on the PR; merging deploys to prod
```

Verify the deploy landed, then confirm what's actually running:

```bash
kubectl -n pae-backend-ot-prod rollout status deploy/pae-backend-ot
kubectl -n pae-backend-ot-prod get deploy pae-backend-ot \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'   # image SHA now live
```

That SHA should match `newTag` in `k8s/overlays/prod/kustomization.yaml`. If it
doesn't, ArgoCD hasn't synced yet.

### Emergency

```bash
# roll back fast: edit newTag in k8s/overlays/prod/kustomization.yaml to a known-good SHA
git commit -am "rollback(prod): pin <sha> [skip ci]" && git push

git revert <sha-of-bad-merge>                  # proper fix, via a PR
kubectl apply -k k8s/overlays/prod             # break-glass, only if ArgoCD is down
```

Always finish by making git match what should be running — ArgoCD's self-heal will
drag the cluster back to whatever git says. Full detail in **6.G**.

---

<a name="1-the-big-picture"></a>
## 1. The big picture (read this first)

### The one idea: GitOps

Everything rests on a single principle:

> **Git is the source of truth for what runs in the cluster.**

You do **not** normally log into the cluster and change things by hand. Instead:

1. You change code and merge it.
2. Automation builds an image and writes the new image's name **back into git**.
3. An agent inside the cluster (**ArgoCD**) notices git changed and makes the
   cluster match git.

So **"deploying" = "making a commit that changes what git says should run."**

### Two halves: CI and CD

- **CI (Continuous Integration)** = automation that *checks* every change: lint,
  tests, trial build, manifest validation. Answers *"is this change safe?"* It
  never touches the cluster. File: `.github/workflows/ci.yml`.
- **CD (Continuous Delivery)** = automation that *ships* a change: build the image,
  push it, update git. Answers *"get it running."* File:
  `.github/workflows/cd-prod.yml`.

### The sequence of one prod deploy, start to finish

1. **You merge code** into the `main` branch on GitHub.
2. **CI runs** (`ci.yml`): lint, tests, trial build, manifest check → green/red.
3. **CD runs** (`cd-prod.yml`) because the push was to `main`.
4. CD **authenticates to Google Cloud** using Workload Identity Federation
   (keyless — no stored password).
5. CD **builds the container image** from your code.
6. CD **pushes the image** to Artifact Registry, tagged with the git commit SHA
   (e.g. `pae-backend-ot:a1b2c3d`).
7. CD **writes that tag into git** — edits `k8s/overlays/prod/kustomization.yaml`
   and commits it with `[skip ci]`. **This commit is the deploy order.**
8. **ArgoCD (inside the cluster) notices** the new commit.
9. ArgoCD **runs the migration Job first** (updates the database schema). If it
   fails, the deploy stops and the old version keeps running.
10. ArgoCD **rolls out the new pods**; GKE pulls the image and starts them; new
    pods must pass `/api/readyz` before old pods are removed.
11. **Running in prod.** ArgoCD shows *Healthy / Synced*.

**The key handoff:** GitHub's job ends at step 7 (it edits git). From step 8 on,
the cluster pulls the change to itself. **GitHub never reaches into the cluster.**

### Why this design (what it buys you)

- **No cluster credentials in GitHub.** A leaked GitHub token can't touch prod.
- **Self-healing.** If someone hand-edits prod, ArgoCD reverts it to match git.
- **Audit + rollback for free.** Every deploy is a git commit you can read and revert.

### Branch → environment map

| Branch    | Workflow      | Overlay             | Namespace          | ArgoCD app             |
|-----------|---------------|---------------------|--------------------|------------------------|
| `main`    | `cd-prod.yml` | `k8s/overlays/prod` | `pae-backend-ot-prod` | `pae-backend-ot-prod` |
| `feat/*`  | `ci.yml` only | —                   | —                  | — (never deploys)      |

`main` is the only long-lived branch and the only one that deploys. Feature
branches run CI via their pull request and deploy nothing until merged.

There is **no dev/staging environment**. If you add one later, it's a second
overlay + a copy of `cd-prod.yml` + real GCP resources (Cloud SQL, Memorystore,
namespace) — the overlay alone does nothing without them.

---

<a name="2-glossary"></a>
## 2. Glossary — every term and its job

**Artifact** — any built output made from source code that you store and reuse.
Here, the main artifact is the container image. You *edit* source; you *build and
store* artifacts.

**Container image (or "image")** — a frozen, portable package holding your app plus
everything it needs to run (Python, libraries, your code). Built by `docker build`
from the `Dockerfile`. Think "a snapshot you can start anywhere."

**Container** — a *running instance* of an image. Image = recipe; container = the
cooked meal. One image can start many containers (that's how replicas work).

**Registry / Artifact Registry** — a storage server for images. **Artifact
Registry** is Google Cloud's managed one. CD **pushes** (uploads) images there;
GKE **pulls** (downloads) them.

**Tag** — a label on an image, written `name:tag`. We use the git commit SHA as the
tag so each image is **immutable** — `a1b2c3d` always means exactly that code.
(Avoid `:latest`; its meaning changes over time.)

**Commit / SHA** — a saved change in git, identified by a unique hash (the SHA). We
reuse that SHA as the image tag so a running image traces back to exact source.

**Workflow** — a GitHub Actions automation file (in `.github/workflows/`) that runs
on an event (e.g. "push to main"). CI and CD are each workflows.

**GKE (Google Kubernetes Engine)** — Google's managed Kubernetes. Kubernetes is the
system that runs and supervises your containers across machines.

**Kubernetes manifest** — a YAML file describing a desired cluster object (a
Deployment, Service, etc.). You declare *what you want*; Kubernetes makes reality
match.

**Kustomize / base / overlay** — a tool to reuse manifests without copy-paste.
`k8s/base/` holds shared manifests; an **overlay** (`k8s/overlays/prod`) patches
the base with environment-specific values. "Rendering" = `kustomize build`
combining base + overlay into final YAML. One overlay per environment; today
there is only `prod`.

**Namespace** — a virtual partition inside one cluster. Ours is
`pae-backend-ot-prod`; a second environment would get its own namespace so its
objects stay isolated even on the same cluster.

**Deployment** — the Kubernetes object that runs your app pods, keeps the desired
number alive, and does rolling updates (new pods up before old pods down).

**Pod** — the smallest runnable unit in Kubernetes: one or more containers that live
together. Here: the app container + the Cloud SQL Auth Proxy sidecar.

**Sidecar** — a helper container running beside the main app in the same pod. Ours
is the **Cloud SQL Auth Proxy**, giving the app a secure `localhost:5432` tunnel to
the database.

**Job** — a run-to-completion task (not a long-running server). Our **migration
Job** runs `scripts/migrate_db.py` once, then exits.

**PreSync hook** — an ArgoCD instruction meaning "run this *before* applying the
rest." That's how the migration Job runs before the app rolls out.

**ConfigMap / Secret** — Kubernetes objects holding configuration. **ConfigMap** =
non-secret settings (hosts, ports, log level). **Secret** = sensitive values (the
two passwords). The Secret comes from GCP Secret Manager and is never stored in git.

**ArgoCD** — the GitOps agent living inside the cluster. It continuously
**reconciles**: compares git (desired) with the cluster (actual) and changes the
cluster to match. If someone hand-edits prod, it reverts them — git always wins.

**Sync / reconcile** — ArgoCD's act of making the cluster match git. Can be
automatic or triggered manually.

**GitOps** — the overall philosophy: git is the single source of truth for
infrastructure; you deploy by changing git; an agent applies it.

**Rollout / rollback** — *rollout* = gradual replacement of old pods with new.
*rollback* = returning to a previous version (see [section 4](#4-deploy--commit)).

**Workload Identity Federation (WIF)** — keyless authentication. GitHub proves who
it is to GCP and gets a short-lived token, so no long-lived key is ever stored.

**Workload Identity (in-cluster)** — the same idea inside GKE: a pod's Kubernetes
identity is mapped to a Google identity, so the Cloud SQL proxy can authenticate
without a key file.

**HPA (HorizontalPodAutoscaler)** — automatically adds/removes pod replicas based on
load (CPU here).

**PDB (PodDisruptionBudget)** — guarantees a minimum number of pods stay up during
disruptions (e.g. node maintenance).

**Cloud SQL** — Google's managed PostgreSQL. **Memorystore** — Google's managed
Redis. **Secret Manager** — Google's managed secret store.

---

<a name="3-the-artifact-chain"></a>
## 3. The artifact chain — what actually flows

### Why we package the code at all

A bare server doesn't have Python, your libraries, or your files. So we **package**
everything the app needs into one portable bundle — the **image** (the artifact).
It runs identically on your laptop, in CI, and in prod. That sameness is the point.

### The crucial insight: two things flow on two paths, and meet at the cluster

**Path 1 — the heavy image itself:**
```
your code ──docker build──► image ──docker push──► Artifact Registry
```
The actual bytes go to the registry and *stay there*. They do **not** flow through
git.

**Path 2 — a lightweight pointer (just the tag, a few characters):**
```
CD writes "newTag: a1b2c3d" ──git commit──► the repo (k8s/overlays/prod)
```
Only a *reference* to the image goes into git. Git never holds the image.

**They meet in the cluster:**
```
ArgoCD reads the pointer from git ──────────┐
                                            ├─► GKE pulls image a1b2c3d from
Artifact Registry holds the actual image ───┘   Artifact Registry, then runs it
```

So: **the image goes to the registry; the *name* of the image goes to git; the
cluster reads the name from git and fetches the image from the registry.** That
separation is exactly why GitHub needs no cluster access.

### Each actor's job

| Stage              | Actor                    | Its job                                          |
|--------------------|--------------------------|--------------------------------------------------|
| Write code         | you                      | change source, merge to `main`/`dev`             |
| Build image        | GitHub Actions (cd-*.yml)| run `docker build`                               |
| Store image        | Artifact Registry        | keep the image, addressable by `name:sha`        |
| Record the pointer | GitHub Actions           | `kustomize edit set image` → commit the new tag  |
| Detect the change  | ArgoCD (in cluster)      | compare git vs cluster; differ → sync            |
| Prepare the DB     | migration Job (PreSync)  | run `migrate_db.py` once before the app rolls    |
| Pull & run         | GKE                      | pull image by tag, start pods, replace old ones  |

---

<a name="4-deploy--commit"></a>
## 4. Deploy = a git commit. Rollback = a commit too.

### Why a deploy is a commit

The last step of CD **edits a file in git and commits it**. The file is
`k8s/overlays/prod/kustomization.yaml`; the changed line is the image tag:

```yaml
images:
  - name: pae-backend-ot
    newName: us-central1-docker.pkg.dev/MY_PROJECT_ID/pae/pae-backend-ot
    newTag: a1b2c3d          # ← changes every deploy
```

Afterwards `git log` on `main` shows:

```
chore(prod): deploy pae-backend-ot a1b2c3d [skip ci]   ← the deploy record
Merge pull request #42 from feature/new-endpoint        ← your code change
```

That first commit **is the deployment record**: at this time, prod moved to image
`a1b2c3d`. You never have to guess what's running — you read git.

### Rollback — the accurate version (important nuance)

Our CD rebuilds on **every** push to `main`. So naively reverting the deploy commit
would just make CD rebuild the latest code and redeploy it — undoing your rollback.
Use one of these instead:

**Option 1 — Fast: pin prod to a known-good image (no rebuild).** Recommended when
prod is broken and you need it fixed now.
```bash
# edit k8s/overlays/prod/kustomization.yaml -> newTag: <previous-good-sha>
git commit -am "rollback(prod): pin <previous-good-sha> [skip ci]"
git push
```
The `[skip ci]` stops CD from rebuilding; ArgoCD deploys the old image (still in the
registry — images are immutable and kept). This is itself an auditable commit.

**Option 2 — Proper: fix-forward by reverting the code.**
```bash
git revert <sha-of-the-bad-code-merge>   # via a PR into main
```
CI + CD rebuild from the corrected code and deploy it. Slower but keeps code and
deployment perfectly in sync.

**Option 3 — Emergency: ArgoCD UI rollback.** In the ArgoCD dashboard →
*History and Rollback* → pick a previous revision. You must **pause auto-sync**
first, or ArgoCD will immediately re-sync forward. Use this only to stop the
bleeding, then do Option 1 or 2 so git matches reality.

> **Golden rule:** always finish by making git reflect what should be running, or
> ArgoCD's self-heal will drag the cluster back to whatever git says.

---

<a name="5-secrets"></a>
## 5. Where credentials & secrets live

There are four different kinds of secret; they are handled very differently.

| Secret / credential                    | Local                                   | Dev & Prod (GKE)                                                    |
|----------------------------------------|-----------------------------------------|--------------------------------------------------------------------|
| **DB password** (`POSTGRES_PASSWORD`)  | `.env` on your laptop (git-ignored)     | GCP **Secret Manager** → copied into a k8s **Secret** in the namespace → app reads it via `envFrom` |
| **Redis password**                     | none (local Redis has no auth)          | k8s Secret, only if Memorystore AUTH is on                         |
| **Reaching the database over the net** | direct to the local Postgres container  | **Cloud SQL Auth Proxy** sidecar, authenticated by the pod's Google identity (Workload Identity) |
| **GitHub → Google Cloud** (push image) | not needed                              | **Workload Identity Federation** — keyless, short-lived token       |
| **Cluster → registry** (pull image)    | not needed                              | GKE's Google service account has Artifact Registry read access      |
| **ArgoCD → git** (read manifests)      | not needed                              | a read token/deploy key in ArgoCD (only if the repo is private)     |

### The two database credentials people confuse

1. **Instance access** — "can this pod open a connection to this Cloud SQL
   instance?" Handled by the **Cloud SQL Auth Proxy** using the pod's Google
   identity. No password; it's IAM.
2. **Database login** — "which Postgres user, what password?" The app logs in as
   `pae_backend_ot_user` with `POSTGRES_PASSWORD` over the proxy tunnel. *This* password lives
   in Secret Manager → k8s Secret.

The proxy secures the *pipe*; the password authenticates the *user* inside it. The
app needs both.

### The golden rules

- **Secrets never go in git.** Not in manifests, the overlay, or the image. The
  committed `k8s/base/secret.example.yaml` is a *template* with `REPLACE_ME` and is
  deliberately left out of the Kustomize `resources:` list so it can't be applied
  by accident.
- **Local uses `.env`; cloud uses Secret Manager.** `.env` is git-ignored and only
  on your machine. A committed `.env.example` documents every variable.
- **`config.py` requires `POSTGRES_PASSWORD`.** If it's missing, the app refuses to
  start — a loud crash, not a silent bad connection.

---

<a name="5b-who"></a>
## 5b. Who creates what — humans (once) vs. automation (forever)

A common confusion: which of these do *you* create, and which happen by themselves?
There are only **two kinds of "who"** in this system:

1. **You, a human admin, during one-time setup** (sections 6.A–6.C). Because you're
   solo with the `Owner` role, that's just you. Done once, never again.
2. **Automation, forever after** — the `gh-deployer` service account (pushes images)
   and **ArgoCD** (syncs the cluster). These are *identities*, not people, and you
   created them in step 1.

| Component | What it is | Who creates it | How | How often |
|---|---|---|---|---|
| **Artifact Registry** | Storage repo for images | You (Owner) | `gcloud artifacts repositories create` (A3) or Console | Once |
| **Secret Manager entry** | The stored DB password | You (Owner) | `gcloud secrets create` (A7) or Console | Once, then on rotation (6.H) |
| **Memorystore AUTH** | *Optional* Redis password | You, at instance creation | `--enable-auth` on A6, then `get-auth-string` | Optional, once (off by default) |
| **Cloud SQL Auth Proxy** | A sidecar *container*, not a cloud resource | **Nobody** — it ships in the manifests | You only supply `INSTANCE_CONNECTION_NAME` (C1) + the WIF binding (A8); k8s/ArgoCD runs it | Automatic, every pod start |
| **Workload Identity Federation** | Keyless GitHub↔GCP trust | You, two sides | GCP: `gcloud iam workload-identity-pools ...` (A9); GitHub: paste values into repo Secrets (B2) | Once |
| **ArgoCD** | The GitOps agent in the cluster | You (cluster admin) | Install once: `kubectl apply .../install.yaml` (C4); then *register* this app: `kubectl apply application-prod.yaml` (C5) | Install once; runs forever |

Two things that feel like resources but **aren't created by anyone**: the **Cloud SQL
Auth Proxy** (a container shipped inside your pods — you configure it, you don't create
it) and the **ArgoCD `Application`** for this service (you *register* it once in C5;
ArgoCD then keeps it running).

---

<a name="6-procedures"></a>
## 6. Procedures — grouped by how often you do them

Replace `MY_PROJECT_ID` with your real GCP project ID everywhere, and
`my-org/pae-backend-ot` with your real GitHub repo. Region is `us-central1`
throughout — change if you use another.

<a name="60-tools"></a>
### 6.0 Step 0 — install your tools (once per laptop)

You need four command-line tools: **git**, **Docker Desktop**, the **Google Cloud CLI
(`gcloud`)**, and **kubectl**. Commands below are for **Windows PowerShell**.

> **The #1 gotcha:** after installing a tool, its command isn't recognized until you
> **open a brand-new PowerShell window.** An installer updates your PATH, but windows
> that were already open don't see the change. If you hit
> `'gcloud' is not recognized...`, that's this — close the terminal and open a new one.

- [ ] **git** — you already have it (you clone/commit this repo). Verify:
  ```powershell
  git --version
  ```

- [ ] **Docker Desktop** — builds and runs images locally.
  ```powershell
  winget install Docker.DockerDesktop
  ```
  Or download from https://www.docker.com/products/docker-desktop. **Then launch
  Docker Desktop from the Start menu once** and wait until it says "running" (it must
  be running for any `docker`/compose command). Verify in a **new** terminal:
  ```powershell
  docker version
  ```

- [ ] **Google Cloud CLI (`gcloud`)** — talks to Google Cloud.
  ```powershell
  winget install Google.CloudSDK
  ```
  Or download `GoogleCloudSDKInstaller.exe` from
  https://cloud.google.com/sdk/docs/install (keep "add gcloud to PATH" checked).
  **Open a new terminal**, then verify and log in:
  ```powershell
  gcloud version
  gcloud auth login                     # opens a browser; sign in with your Google account
  ```
  (You'll set the project in section 6.0b, after you create one.)

- [ ] **kubectl** — talks to the Kubernetes cluster. Easiest is via gcloud:
  ```powershell
  gcloud components install kubectl
  ```
  Verify in a **new** terminal:
  ```powershell
  kubectl version --client
  ```

> If `winget` itself isn't recognized, it comes from "App Installer" — install it once
> from the Microsoft Store (search "App Installer"), or just use the download-installer
> link given for each tool instead.

---

<a name="60-account"></a>
### 6.0b Before the cloud setup — GCP account, project, billing, permissions (one-time)

Section 6.A assumes a **billed GCP project exists and you have admin rights on it.**
Since you're doing this solo, that admin is **you** — do these first. Each can be done
in the web **Console** (https://console.cloud.google.com) or with `gcloud`; both shown.

- [ ] **P1. A Google account with access to Google Cloud.** Sign in once at
  https://console.cloud.google.com and accept the terms.
- [ ] **P2. Create (or choose) a project.** A "project" is the container that owns
  every resource and gets billed. Its **ID** (not the display name) is your
  `MY_PROJECT_ID`.
  - Console: top-bar project dropdown → **New Project** → note the **Project ID**.
  - CLI — create a new one:
    ```bash
    gcloud projects create MY_PROJECT_ID --name="PAE Backend OT"
    ```
  - **See all your projects (IDs and names):**
    ```bash
    gcloud projects list
    # PROJECT_ID (left column) is what you use — NOT PROJECT_NUMBER
    ```
  - **Set the active project, and check it:**
    ```bash
    gcloud config set project MY_PROJECT_ID      # e.g. prd-pae-backend-ot
    gcloud config get-value project              # confirm it shows the ID
    ```
  - **Gotcha:** you must set the project **ID** (a string), not the numeric
    **project number**. If a command errors with *"core/project property is set to
    project number… set core/project to PROJECT ID"*, re-run
    `gcloud config set project MY_PROJECT_ID` using the ID from `gcloud projects list`.
  - **Housekeeping — delete a project you don't need** (stops its billing; ~30-day
    undo with `gcloud projects undelete PROJECT_ID`):
    ```bash
    gcloud projects delete PROJECT_ID
    ```
- [ ] **P3. Link a billing account.** **Required** — creating GKE, Cloud SQL, or
  Memorystore fails without it (they cost money; a free-trial credit works).
  - **Console (browser):**
    1. Go to https://console.cloud.google.com/billing and sign in.
    2. Under **My Billing Accounts**, note your account **ID** (`01ABCD-234567-89EFGH`).
       If the list is empty, click **Add billing account** → Individual → add a
       payment method (card; new accounts usually get free-trial credit).
    3. In the top bar select your project (`MY_PROJECT_ID`), then **☰ menu → Billing**.
    4. If unlinked you'll see **"This project has no billing account"** →
       **Link a billing account** → pick your account → **Set account**.
    5. Verify under **Billing → Account management → Projects** that your project is listed.
  - **CLI (if you already have a billing account ID):**
    ```bash
    gcloud billing accounts list                       # find your ACCOUNT_ID
    gcloud billing projects link MY_PROJECT_ID --billing-account=ACCOUNT_ID
    ```
- [ ] **P4. Confirm you have admin rights.** Section 6.A creates many resource types,
  so you need broad rights. The simplest is the **Owner** role. If you created the
  project you already have it; otherwise check Console → **IAM & Admin → IAM** that
  your account shows `Owner`. Without this, `gcloud ... create` calls fail with
  "permission denied."
- [ ] **P5. Networking (usually nothing to do).** GKE Autopilot and Memorystore both
  use the project's **`default`** VPC network out of the box, which is what 6.A relies
  on. Only act if the default network was deleted or your project uses a custom/Shared
  VPC — then the cluster and the Redis instance must be placed on the **same** network
  or the Redis private IP won't be reachable. Cloud SQL needs no VPC setup here: the
  Auth Proxy connects out over the internet using IAM.

Once P1–P4 are done and `gcloud config get-value project` shows your project, continue
to 6.A.

---

<a name="6a-gcp"></a>
### 6.A One-time setup — GCP & GKE infrastructure

> **Which shell?** The blocks below use **Bash** syntax. Most single-line `gcloud`
> commands also run fine in **PowerShell**, but a few use Bash-only bits — line
> continuations (`\`), `printf`, and `$(...)` substitution — that PowerShell handles
> differently. Easiest path on Windows: **run 6.A–6.C in Git Bash** (installed with
> Git; open "Git Bash" from the Start menu). Where a command needs a different
> PowerShell form, a **PowerShell** variant is shown (e.g. A7, C3).

You can run the whole thing with the helper script (needs Bash — use Git Bash on Windows):
```bash
PROJECT_ID=MY_PROJECT_ID GITHUB_REPO=my-org/pae-backend-ot bash scripts/gcp_bootstrap.sh
```
…or do it step by step to understand each piece:

- [ ] **A1. Point gcloud at the project**
  ```bash
  gcloud config set project MY_PROJECT_ID
  ```
- [ ] **A2. Enable the Google services** (APIs are off by default)
  ```bash
  gcloud services enable container.googleapis.com artifactregistry.googleapis.com \
    sqladmin.googleapis.com secretmanager.googleapis.com redis.googleapis.com \
    iamcredentials.googleapis.com sts.googleapis.com
  ```
- [ ] **A3. Create the image registry** (the warehouse for images)
  ```bash
  gcloud artifacts repositories create pae --repository-format=docker --location=us-central1
  ```
- [ ] **A4. Create the cluster** (Autopilot = Google manages the servers; takes minutes)
  ```bash
  gcloud container clusters create-auto pae-autopilot --region=us-central1
  ```
- [ ] **A5. Create the database and note its connection name.** `--edition=ENTERPRISE`
  is required — without it Cloud SQL defaults to Enterprise Plus, which rejects custom
  tiers like `db-custom-1-3840` (1 vCPU / 3.75 GB). For an even cheaper box, use
  `--tier=db-g1-small`.
  ```bash
  gcloud sql instances create pae-backend-ot-pg-prod --database-version=POSTGRES_16 \
    --region=us-central1 --edition=ENTERPRISE --tier=db-custom-1-3840 --storage-auto-increase
  gcloud sql databases create pae_backend_ot --instance=pae-backend-ot-pg-prod
  gcloud sql users create pae_backend_ot_user --instance=pae-backend-ot-pg-prod --password='PICK_A_STRONG_PASSWORD'
  gcloud sql instances describe pae-backend-ot-pg-prod --format='value(connectionName)'
  # SAVE the output, e.g. my-project:us-central1:pae-backend-ot-pg-prod
  ```
- [ ] **A6. Create Redis and note its private IP**
  ```bash
  gcloud redis instances create pae-backend-ot-redis-prod --size=1 --region=us-central1 \
    --redis-version=redis_7_0 --network=default
  gcloud redis instances describe pae-backend-ot-redis-prod --region=us-central1 --format='value(host)'
  # SAVE the IP, e.g. 10.12.34.5
  ```
  `--network=default` puts Redis on the same VPC as the Autopilot cluster so pods can
  reach that private IP (see P5). **AUTH (a Redis password) is optional and off here** —
  the VPC already isolates Redis, and our k8s Secret leaves `REDIS_PASSWORD` empty. To
  turn it on instead, add `--enable-auth` above, then read the password and store it in
  the k8s Secret:
  ```bash
  gcloud redis instances get-auth-string pae-backend-ot-redis-prod --region=us-central1
  # put that value into REDIS_PASSWORD when you create pae-backend-ot-secrets (C3)
  ```
- [ ] **A7. Store the DB password in Secret Manager.** Use the **exact same** password
  you set on `pae_backend_ot_user` in A5.
  - **Bash / Git Bash:**
    ```bash
    printf 'PICK_A_STRONG_PASSWORD' | gcloud secrets create pae-backend-ot-postgres-password --data-file=-
    ```
  - **Windows PowerShell** (`printf` doesn't exist there; write to a temp file with no
    trailing newline, which would otherwise corrupt the password):
    ```powershell
    $pw = 'PICK_A_STRONG_PASSWORD'
    [System.IO.File]::WriteAllText("$env:TEMP\pw.txt", $pw)
    gcloud secrets create pae-backend-ot-postgres-password --data-file="$env:TEMP\pw.txt"
    Remove-Item "$env:TEMP\pw.txt"
    ```
- [ ] **A8. Let the app's pods reach Cloud SQL (Workload Identity for the proxy)**
  ```bash
  gcloud iam service-accounts create pae-backend-ot-prod --display-name="pae-backend-ot prod SQL client"
  gcloud projects add-iam-policy-binding MY_PROJECT_ID \
    --member="serviceAccount:pae-backend-ot-prod@MY_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"
  gcloud iam service-accounts add-iam-policy-binding \
    pae-backend-ot-prod@MY_PROJECT_ID.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="serviceAccount:MY_PROJECT_ID.svc.id.goog[pae-backend-ot-prod/pae-backend-ot]"
  ```
- [ ] **A9. Let GitHub push images without a stored key (WIF)**
  ```bash
  gcloud iam service-accounts create gh-deployer --display-name="GitHub Actions deployer"
  gcloud projects add-iam-policy-binding MY_PROJECT_ID \
    --member="serviceAccount:gh-deployer@MY_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"
  gcloud iam workload-identity-pools create github --location=global
  gcloud iam workload-identity-pools providers create-oidc github --location=global \
    --workload-identity-pool=github \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='my-org/pae-backend-ot'" \
    --issuer-uri="https://token.actions.githubusercontent.com"
  POOL=$(gcloud iam workload-identity-pools describe github --location=global --format='value(name)')
  gcloud iam service-accounts add-iam-policy-binding \
    gh-deployer@MY_PROJECT_ID.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL}/attribute.repository/my-org/pae-backend-ot"
  gcloud iam workload-identity-pools providers describe github --location=global \
    --workload-identity-pool=github --format='value(name)'
  # SAVE this long string → it is GCP_WORKLOAD_IDENTITY_PROVIDER for GitHub
  ```

**At the end of 6.A you should have saved:** the SQL connection name (A5), the Redis
IP (A6), and the WIF provider string (A9). The deployer email is
`gh-deployer@MY_PROJECT_ID.iam.gserviceaccount.com`.

---

<a name="6b-github"></a>
### 6.B One-time setup — GitHub configuration (in your browser)

- [ ] **B1. Add repository Variables.** Repo → **Settings** → left sidebar
  **Secrets and variables** → **Actions** → **Variables** tab → **New repository
  variable**. Add four:
  - `GCP_PROJECT_ID` = `MY_PROJECT_ID`
  - `GCP_REGION` = `us-central1`
  - `AR_HOST` = `us-central1-docker.pkg.dev`
  - `AR_REPO` = `pae`
- [ ] **B2. Add repository Secrets.** Same page → **Secrets** tab → **New repository
  secret**. Add two:
  - `GCP_WORKLOAD_IDENTITY_PROVIDER` = the long provider string from A9
  - `GCP_DEPLOY_SERVICE_ACCOUNT` = `gh-deployer@MY_PROJECT_ID.iam.gserviceaccount.com`
- [ ] **B3. Protect `main` (branch ruleset).** Repo → **Settings** → **Branches** →
  **Add branch ruleset** → target `main`. `main` is the only long-lived branch, so
  this is the only ruleset you need. It interacts with CD, because **`cd-prod.yml`
  pushes the image-tag-bump commit directly to `main`** (with `[skip ci]`).

  Always enable these — they don't block direct pushes, so CD keeps working:
  - ✅ **Block force pushes** — prevents history rewrites on `main`.
  - ✅ **Restrict deletions** — `main` can't be deleted.

  With the `feat/*` → PR → `main` workflow, also enable:
  - ✅ **Require a pull request before merging**
  - ✅ **Require status checks to pass** — select the **CI** checks.

  ⚠️ Both of those block direct pushes to `main`, which would break CD's tag-bump
  commit. You must pick one fix or prod deploys will start failing:
  - add the GitHub Actions bot to the ruleset's **bypass list** (simplest), **or**
  - change `cd-prod.yml` to open a PR for the tag bump instead of pushing, **or**
  - move image-tag updates to ArgoCD Image Updater so CI never writes to `main`.

  Note the `[skip ci]` bump commit runs no checks, so a status-check rule has
  nothing to see on it — the bypass list is what makes it through.

  Optionally add **Require signed commits** (needs commit-signing setup) and, once
  real tests exist, code-scanning / coverage gates.

---

<a name="6c-cluster"></a>
### 6.C One-time setup — bootstrap the cluster

- [ ] **C1. Fill the `REPLACE_*` placeholders** in `k8s/overlays/prod/kustomization.yaml`:
  - image `newName` → `us-central1-docker.pkg.dev/MY_PROJECT_ID/pae/pae-backend-ot`
  - `REDIS_HOST` → the Redis IP from A6
  - `INSTANCE_CONNECTION_NAME` (appears twice) → the SQL connection name from A5
  - the ServiceAccount annotation project → `MY_PROJECT_ID`

  And in `k8s/argocd/application-prod.yaml`: set `repoURL` → your git URL. Commit and
  push these to `main`.
- [ ] **C2. Connect kubectl to the cluster**
  ```bash
  gcloud container clusters get-credentials pae-autopilot --region us-central1
  kubectl get nodes            # lists nodes → you're connected
  ```
- [ ] **C3. Create the namespace and the app Secret** (the one thing not in git)
  - **Bash / Git Bash:**
    ```bash
    kubectl create namespace pae-backend-ot-prod
    kubectl -n pae-backend-ot-prod create secret generic pae-backend-ot-secrets \
      --from-literal=POSTGRES_PASSWORD="$(gcloud secrets versions access latest --secret=pae-backend-ot-postgres-password)" \
      --from-literal=REDIS_PASSWORD=""
    ```
  - **Windows PowerShell** (no `\` continuations; capture the password first):
    ```powershell
    kubectl create namespace pae-backend-ot-prod
    $pgpw = gcloud secrets versions access latest --secret=pae-backend-ot-postgres-password
    kubectl -n pae-backend-ot-prod create secret generic pae-backend-ot-secrets --from-literal=POSTGRES_PASSWORD="$pgpw" --from-literal=REDIS_PASSWORD=""
    ```
- [ ] **C4. Install ArgoCD** (once per cluster)
  ```bash
  kubectl create namespace argocd
  kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  ```
  Optional — open the ArgoCD UI. First get the initial admin password:
  - **Bash / Git Bash:**
    ```bash
    kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
    ```
  - **Windows PowerShell** (no `base64` command; decode via .NET — kept as a single
    line so it can't break when pasted):
    ```powershell
    [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String((kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}")))
    ```
  Then, in a **separate terminal** (this command blocks to keep the tunnel open):
  ```bash
  kubectl -n argocd port-forward svc/argocd-server 8080:443
  ```
  **Log in at https://localhost:8080:**
  - **Username:** `admin`
  - **Password:** the auto-generated `argocd-initial-admin-secret` value. Reprint it
    anytime with (PowerShell):
    ```powershell
    [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String((kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}")))
    ```
  - The browser warns about the self-signed cert → **Advanced → proceed**.
  - Keep the `port-forward` terminal running while using the UI (Ctrl+C drops it).
  - Recommended once in: change the password (**User Info → Update Password**), then
    delete the initial secret: `kubectl -n argocd delete secret argocd-initial-admin-secret`.

  **If your repo is private, connect it before C5** (else the Application shows
  `ComparisonError: repository not accessible`):

  1. **Create a GitHub token (read-only on this repo).** GitHub → **Settings** →
     **Developer settings** → **Personal access tokens** → **Fine-grained tokens** →
     **Generate new token**. Name it `argocd-pae-backend-ot`, set an expiration, **Resource
     owner** = your account, **Repository access** = *Only select repositories* →
     this repo, and **Repository permissions** → **Contents: Read-only**. Generate and
     copy the token (`github_pat_...`) — shown only once.
     (Classic-token alternative: Tokens (classic) → scope `repo`.)
  2. **Connect it in ArgoCD.** UI → **Settings → Repositories → + CONNECT REPO** →
     method **VIA HTTPS**:
     - Type `git`, Project `default`
     - Repository URL: `https://github.com/<owner>/<repo>.git`
     - Username: your GitHub username (any non-empty value; the token authenticates)
     - Password: the token from step 1
     - **CONNECT** → the row should read **Connection status: Successful**.
- [ ] **C5. Register the app with ArgoCD.** Run this **from the repo root** — the
  `k8s/...` path is relative, so it fails with "path does not exist" if your shell is
  elsewhere (your prompt shows the current folder; `~` means home, not the repo).
  ```bash
  cd "C:\Users\yazda\OneDrive\Desktop\pae-microservices-dev\pae-backend-ot"
  kubectl apply -f k8s/argocd/application-prod.yaml
  ```
  (Or from anywhere, use the full path:
  `kubectl apply -f "C:\...\pae-backend-ot\k8s\argocd\application-prod.yaml"`.)
  Expected: `application.argoproj.io/pae-backend-ot-prod created`. Then check it:
  ```bash
  kubectl -n argocd get applications
  ```
  > The same "run from the repo root" rule applies to every `kubectl ... -f k8s/...`,
  > `kubectl apply -k k8s/...`, and `make`/`.\make.ps1` command.
- [ ] **C6. Verify**
  ```bash
  kubectl -n pae-backend-ot-prod get pods           # app + sidecar Running
  kubectl -n pae-backend-ot-prod port-forward svc/pae-backend-ot 8000:8000
  # in another terminal:
  curl http://localhost:8000/api/readyz          # {"ready":true,...}
  ```

Prod is now live and self-managing.

---

<a name="6d-prod"></a>
### 6.D DAILY — deploy to PROD

Once 6.A–6.C are done, this is the whole routine:

1. `git checkout main && git pull`
2. Make your change on a branch; open a Pull Request into `main`.
3. Wait for the **CI** check on the PR to go green. Merge.
4. **`cd-prod.yml` runs automatically**: builds the image, pushes it, bumps the tag
   in `overlays/prod`, commits `[skip ci]`.
5. **ArgoCD syncs** within a couple of minutes (or click *Sync* in the UI).
6. Verify:
   ```bash
   kubectl -n pae-backend-ot-prod rollout status deploy/pae-backend-ot
   ```
   then check `/api/readyz` as in C6.

**To deploy to prod: merge to `main`. Nothing else.**

---

<a name="6e-feature"></a>
### 6.E DAILY — work on a feature

`main` is the only long-lived branch. Every feature is a short-lived branch that
goes back into `main` through a pull request:

```bash
git checkout main
git pull origin main                 # always start from what's in prod
git checkout -b feat/short-name

# ...edit, commit...

git push -u origin feat/short-name
gh pr create --base main             # CI runs on the PR
```

Merging the PR is what deploys — see 6.D. Delete the branch after merge
(`git push origin --delete feat/short-name`).

**There is no dev environment to test in first.** Verify locally (6.F) and rely
on CI plus PR review before merging; merging to `main` goes straight to prod.
That is the tradeoff of a single-environment setup — if it starts to hurt, add a
staging overlay rather than a long-lived branch.

---

<a name="6f-local"></a>
### 6.F DAILY — run locally (no cloud at all)

```powershell
docker network create pae-shared-network      # once, first time only
copy .env.example .env                         # then edit .env and set POSTGRES_PASSWORD
.\make.ps1 up-build                            # builds & starts postgres + redis + app
```
Check health:
```powershell
Invoke-WebRequest http://localhost:8000/api/healthz | Select-Object -Expand Content
```
Here Postgres and Redis are throwaway containers on your laptop, the password comes
from `.env`, migrations run automatically inside the container, and GCP is not
involved. Stop with `.\make.ps1 down`.

> Note: `.\make.ps1 health` targets an old URL and always reports "not available."
> Use the `Invoke-WebRequest` line above against `/api/healthz` instead.

---

<a name="6g-rollback"></a>
### 6.G WHEN THINGS BREAK — rollback & emergencies

**Fast — pin prod to the last good image (no rebuild):**
```bash
# find a previous good SHA:
git log --oneline k8s/overlays/prod/kustomization.yaml
#   or:
gcloud artifacts docker images list us-central1-docker.pkg.dev/MY_PROJECT_ID/pae/pae-backend-ot
# edit k8s/overlays/prod/kustomization.yaml -> newTag: <previous-good-sha>
git commit -am "rollback(prod): pin <previous-good-sha> [skip ci]"
git push
```

**Proper — revert the bad code and let the pipeline rebuild:**
```bash
git revert <sha-of-bad-merge>     # via a PR into main
```

**Break-glass — ArgoCD is down, must deploy by hand:**
```bash
gcloud container clusters get-credentials pae-autopilot --region us-central1
kubectl apply -k k8s/overlays/prod
```

**Useful diagnostics:**
```bash
kubectl -n pae-backend-ot-prod get pods                       # are pods Running/Ready?
kubectl -n pae-backend-ot-prod logs deploy/pae-backend-ot    # app logs
kubectl -n pae-backend-ot-prod describe pod <pod-name>        # why a pod won't start
kubectl -n pae-backend-ot-prod get job                        # migration Job status
```

> Always finish by making git reflect what should be running, or ArgoCD's self-heal
> will pull the cluster back to whatever git says.

---

<a name="6h-rotate"></a>
### 6.H OCCASIONAL — rotate the DB password

1. Change the password on the Cloud SQL user:
   ```bash
   gcloud sql users set-password pae_backend_ot_user --instance=pae-backend-ot-pg-prod --password='NEW_STRONG_PASSWORD'
   ```
2. Add a new version in Secret Manager:
   ```bash
   printf 'NEW_STRONG_PASSWORD' | gcloud secrets versions add pae-backend-ot-postgres-password --data-file=-
   ```
3. Recreate the k8s Secret from the new value:
   ```bash
   kubectl -n pae-backend-ot-prod delete secret pae-backend-ot-secrets
   kubectl -n pae-backend-ot-prod create secret generic pae-backend-ot-secrets \
     --from-literal=POSTGRES_PASSWORD="$(gcloud secrets versions access latest --secret=pae-backend-ot-postgres-password)" \
     --from-literal=REDIS_PASSWORD=""
   ```
4. Restart the pods so they pick it up:
   ```bash
   kubectl -n pae-backend-ot-prod rollout restart deploy/pae-backend-ot
   ```

---

<a name="6i-access"></a>
### 6.I ACCESS — reach the ArgoCD UI and the app (port-forward)

Both the ArgoCD server and the app are **ClusterIP** (internal only), so you reach them
through a `kubectl port-forward` tunnel. **`port-forward` is a blocking command** — it
holds the terminal open to keep the tunnel alive. So:
- Run each `port-forward` in its **own terminal** and **leave it open** (don't Ctrl+C /
  close it — that kills the tunnel; "Could not connect to localhost" almost always means
  the tunnel isn't running).
- Run `curl`/your browser in a **separate** terminal.
- If you see `Unable to listen on port …: address already in use`, a dead forward is
  lingering — use a different local port (e.g. `18080`/`18000`).

**ArgoCD UI:**
```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
# leave running → browse https://localhost:8080  (user: admin; accept the cert warning)
```
Get/refresh the admin password (PowerShell):
```powershell
[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String((kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}")))
```

**The app API:**
```bash
kubectl -n pae-backend-ot-prod port-forward svc/pae-backend-ot 8000:8000
# leave running, then in another terminal:
curl http://localhost:8000/api/healthz     # {"ok":true,...}
curl http://localhost:8000/api/readyz       # {"ready":true,...}
```

Prereq: `kubectl` must be pointed at the cluster — if these fail with an auth/context
error, re-run `gcloud container clusters get-credentials pae-autopilot --region us-central1`.

---

<a name="6j-cost"></a>
### 6.J COST CONTROL — stop/start all billable cloud resources

The GKE cluster, Cloud SQL, and (formerly) Memorystore are **always-on** and bill 24/7
whether or not you use them. Redis now runs **in-cluster** (see `k8s/base/redis.yaml`),
so the whole stack can scale to zero. Two commands toggle everything:

```bash
make cloud-down    # or:  .\make.ps1 cloud-down
make cloud-up      # or:  .\make.ps1 cloud-up
```

- **`cloud-down`** scales ArgoCD + app + redis to 0, deletes the HPA (it would
  otherwise force min replicas), and stops Cloud SQL. Idle cost ≈ Cloud SQL storage
  only (~$2–3/mo). **Data is preserved** (Cloud SQL is stopped, not deleted).
- **`cloud-up`** starts Cloud SQL (waits for RUNNABLE), scales ArgoCD back up, scales
  redis + app back up, and nudges ArgoCD to reconcile (recreating the HPA). App is
  ready in ~2–3 min; verify with `/api/readyz` (see 6.I).

Notes:
- Run from a shell where `kubectl` targets the cluster and `gcloud` is authed.
- Override defaults via env/vars if names differ: `GCP_PROJECT`, `GCP_REGION`,
  `SQL_INSTANCE`, `K8S_NS` (Makefile) — the `make.ps1` versions hardcode them near the
  top of each case.
- After `cloud-up`, ArgoCD may briefly show **Progressing** while the HPA gathers CPU
  metrics (~1 min), then goes **Healthy** — that's expected.
- For *absolute* $0 (no Cloud SQL storage charge either) you'd delete the SQL instance
  instead of stopping it, but then `cloud-up` must recreate it + re-run migrations.

---

<a name="7-quickref"></a>
## 7. Quick reference — names, values, files

| Thing                         | Value                                                        |
|-------------------------------|--------------------------------------------------------------|
| GCP region                    | `us-central1`                                                |
| GKE cluster                   | `pae-autopilot`                                              |
| Artifact Registry repo        | `pae` (host `us-central1-docker.pkg.dev`)                    |
| Image name                    | `<AR_HOST>/<PROJECT>/pae/pae-backend-ot`                    |
| Cloud SQL instance / db / user| `pae-backend-ot-pg-prod` / `pae_backend_ot` / `pae_backend_ot_user`                 |
| Memorystore instance          | `pae-backend-ot-redis-prod`                                            |
| Prod namespace                | `pae-backend-ot-prod`                                           |
| k8s ServiceAccount            | `pae-backend-ot`                                            |
| k8s Secret                    | `pae-backend-ot-secrets` (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`) |
| Secret Manager entry          | `pae-backend-ot-postgres-password`                                     |
| GitHub Variables              | `GCP_PROJECT_ID`, `GCP_REGION`, `AR_HOST`, `AR_REPO`         |
| GitHub Secrets                | `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT` |

**Key files in this repo:**

| File                                    | What it is                                        |
|-----------------------------------------|---------------------------------------------------|
| `docker/Dockerfile`                     | how the image is built                            |
| `docker/entrypoint.sh`                  | container startup (migrations toggle)             |
| `.env.example`                          | documents every env var; copy to `.env` locally   |
| `k8s/base/`                             | shared manifests (Deployment, Service, Job, …)    |
| `k8s/overlays/prod`                     | per-environment values                            |
| `k8s/argocd/application-prod.yaml`      | ArgoCD app definition                             |
| `.github/workflows/ci.yml`              | CI (lint, test, build, manifest check)            |
| `.github/workflows/cd-prod.yml`         | CD (build, push, bump tag)                        |
| `scripts/gcp_bootstrap.sh`              | one-shot GCP infra setup                          |
| `scripts/migrate_db.py`                 | database migrations (run by the migration Job)    |

---

*Endpoints:* liveness `GET /api/healthz` (no dependencies), readiness
`GET /api/readyz` (checks Postgres + Redis; returns 503 if either is down).
