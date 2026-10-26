# Deployment status and next steps

Where the deployment stands, how to use it day to day, and what is left before prod goes live.
The full plan and reasoning are in [`PLAN.md`](PLAN.md). Last updated: 2026-10-26.

## Where things stand

| Environment | Where | State |
|---|---|---|
| **local** | the laptop, `make up` | unchanged: every service from source, with the Modbus simulator and powerflow sites |
| **CI** | GitHub Actions (`.github/workflows/ci.yml`) | every PR is checked (changed services, contracts, boundaries); every merge to `main` builds the 4 images and pushes them to Artifact Registry as `pae-<service>:<git sha>` |
| **dev** | GCP `pae-development`, VM `pae-dev` (e2-medium), **public at http://136.115.89.60** (temporary, for demos; see "Public dev") | **deploys itself on every merge to `main`** (`.github/workflows/deploy.yml`). Runs `ce69a5a` with the simulated site `2bess_1pv`; all containers healthy; the e2e check agrees on all 9 devices |
| **prod** | GCP `pae-platform-prod`, VM `pae-prod` (e2-standard-2) | infrastructure ready, **VM stopped** (about $8/month for disks and snapshots); deploys only with the owner's approval |

Done stages (details in `PLAN.md`): 0 cleanup, 1 deployment readiness, 2 CI, 3 infrastructure
(dev and prod), 5 the stack (live on dev), 7 automatic deploys.

## Day to day

| To | Do |
|---|---|
| Ship a change to dev | Merge to `main`. CI runs, then dev updates itself (about 20 minutes) |
| See the pipeline | https://github.com/yazdanimehrdad1/pae-platform/actions (runs), https://github.com/yazdanimehrdad1/pae-platform/deployments (which commit is where) |
| Roll dev back | Actions → Deploy → Run workflow → `dev`, with the older commit's SHA |
| Deploy to prod | Actions → Deploy → Run workflow → `prod`, then **Review deployments** → Approve (prod VM must be running) |
| Open dev's UI | http://136.115.89.60 (public), or privately: `make ui env=dev`, then http://localhost:8080 |
| Check dev | `make status env=dev` (release + container health), `make logs env=dev svc=backend-ot`, `make stats env=dev` |
| Deploy by hand | `make deploy env=dev` (newest `main`) or `make deploy env=dev RELEASE=<sha>` |
| Back up now | `make backup env=dev` (all databases to `gs://pae-development-backups`; weekly runs are automatic) |
| Load a simulated site | `make cloud-seed-site env=dev SITE=2bess_1pv` (dev only) |
| Shell on the server | `make ssh env=dev` |
| Logs in the Console | https://console.cloud.google.com/logs/query?project=pae-development, query `log_id("pae_containers")` |
| Servers in the Console | https://console.cloud.google.com/compute/instances?project=pae-development (and `?project=pae-platform-prod`) |

Plain `make logs` (no `env=`) still follows the local stack.

## What is left

All of these matter mainly for prod; none blocks dev.

| Stage | What | Why |
|---|---|---|
| **4 Public access** | A domain with HTTPS and login, instead of the private IAP tunnel | Needed before clients or the mobile app use it (no service has real auth yet) |
| **6 Site links** | VPN or direct links from the prod VM to the sites' RTACs | prod has nothing to poll until then (`AGGREGATOR_MODBUS_HOST` in `cloud/config/prod.env` is a placeholder) |
| **8 Cost controls** | `make pause` / `resume` / `destroy` per environment | Today: `gcloud compute instances stop pae-dev --project pae-development --zone us-central1-a` |
| **9 Operations** | Alerts (disk above 80%, VM down, container restarting, `/api/readyz` failing), dashboards, a short runbook | Problems show up before someone notices; suggested next, on dev first |

Not in this work (by decision): historian retention or archiving (readings are kept; the disk grows),
multi-site aggregator support, powerflow multi-user isolation, the 20 s vs 10 s poll question.

## Prod go-live checklist

1. Stage 6 done for the first site (the VM can reach its RTAC); set `AGGREGATOR_MODBUS_HOST` in `deploy/cloud/config/prod.env`.
2. Stage 4 decided if anyone outside the team needs access.
3. Start the VM: `gcloud compute instances start pae-prod --project pae-platform-prod --zone us-central1-a`.
4. Add the Anthropic key (and the Open-Meteo commercial key if used) in `pae-platform-prod`: Console → Security → Secret Manager → the secret → New version.
5. `make host-setup env=prod` (data disk, Docker, Ops Agent, backup timer).
6. First deploy: Actions → Deploy → Run workflow → `prod` → Approve. Check with `make status env=prod`.
7. Optional: set the repository variable `PROD_AUTO_PROMOTE=true`, so every dev deploy is offered to prod for approval.

## Owner notes

- `services/backend-ot/Readme-dev/gcloud-notes.md` (untracked) held a plaintext password for the deleted project `prd-pae-rtac-server`: delete the file.
- `prd-pae-rtac-server` can be restored with `gcloud projects undelete prd-pae-rtac-server` until about 2026-11-24; after that it is gone for good.
- Costs now: dev about $32/month while running, prod about $8/month while stopped. Stop dev when unused to save about $24/month.

## Public dev (temporary, since 2026-10-26)

dev is reachable from the internet at **http://136.115.89.60** (a reserved static IP, so the link
on the owner's website keeps working), for demos. Set by `PUBLIC_HTTP=true` for dev in
`deploy/infra/gcp/bootstrap.sh`: firewall rule `pae-allow-public-http` (tcp 80 from anywhere, dev
VM only) and the static IP `pae-dev-public-ip` (about $3.65/month). SSH stays IAP-only; prod
stays private.

What that means while there is no login (Stage 4):
- Anyone with the link can use everything, including changing dev's (simulated) data and asking
  the AI assistant (it spends the Anthropic key's budget; a budget limit is set on the key).
- Plain HTTP: browsers show "Not secure". A domain with HTTPS comes with Stage 4.
- To make dev private again: `PUBLIC_HTTP=false make infra-up env=dev` (removes the rule, the
  public IP and its reservation; the link stops working).
