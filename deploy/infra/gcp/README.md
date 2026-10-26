# Production infrastructure (GCP)

`bootstrap.sh` creates everything the production VM needs in project `pae-platform-prod`
(us-central1) with plain `gcloud` (run from Git Bash on Windows; it uses bash and openssl). It is idempotent: run it again any time; it creates only what is
missing. Plan and reasoning: [`deploy/PLAN.md`](../../PLAN.md) (Stage 3, "Tooling").

```sh
gcloud auth login                 # once, as a project owner
make infra-up env=prod            # = ENV=prod bash deploy/infra/gcp/bootstrap.sh (env=dev for dev)
make ssh env=prod                 # shell on the VM through IAP (no external IP, no SSH keys to manage)
```

## What it creates

| Resource | Name | Notes |
|---|---|---|
| (removed) | the auto-created `default` network and its firewall rules | They open SSH, RDP and ICMP to the whole internet; removed only while no VM uses it |
| VPC + subnet | `pae-vpc`, `pae-usc1` (10.10.0.0/24) | Private Google Access on (GCS, Artifact Registry, Secret Manager without the internet) |
| Firewall | `pae-allow-iap` | tcp 22 and 80 from Google's IAP range `35.235.240.0/20` only; nothing else is open |
| Cloud Router + NAT | `pae-router`, `pae-nat` | Outbound internet for the VM (Claude API, Open-Meteo, Modbus to sites) |
| Service accounts | `pae-prod-vm`, `pae-ci` | No keys. VM: log/metric writer, registry reader, backup bucket object admin, accessor on each secret. CI: registry writer, used through WIF |
| Artifact Registry | `pae` (docker) | `us-central1-docker.pkg.dev/pae-platform-prod/pae/pae-<service>:<git sha>`; keeps the 30 newest versions, deletes older ones after 30 days |
| Backup bucket | `gs://pae-platform-prod-backups` (us-east1) | Private, uniform access; another region than the VM |
| Secrets | `backend-ot-postgres-password`, `intelli-gateway-postgres-password`, `powerflow-postgres-password` | Random values generated once, never printed |
| Secrets (owner fills) | `intelli-gateway-anthropic-api-key`, `intelli-gateway-open-meteo-api-key` | Created empty |
| Workload Identity Federation | pool `github`, provider `github-actions` | Only `yazdanimehrdad1/pae-platform` (matched by its numeric repository and owner ids, which can't be re-registered) on `refs/heads/main` can act as `pae-ci`; a re-run re-applies the condition |
| CD access (each project) | `pae-ci` gets `iap.tunnelResourceAccessor`, `compute.osAdminLogin`, `compute.viewer` and `iam.serviceAccountUser` on the VM's account | Lets `.github/workflows/deploy.yml` reach the VM the same way `make deploy` does (IAP SSH, OS Login with sudo); still no public IP or open port |
| Snapshot schedule | `pae-daily` | Daily 03:00 UTC, 7 kept, on the boot and data disks |
| Data disk | `pae-prod-data` (50 GB pd-balanced) | Holds the Docker volumes (databases); `auto-delete=no`, survives the VM |
| VM | `pae-prod` (e2-standard-2, Debian 12, us-central1-a) | No external IP, OS Login, Shielded VM, deletion protection |

## Public HTTP (`PUBLIC_HTTP`)

`PUBLIC_HTTP=true` (dev's default since 2026-10-26, for demos) reserves a static IP
(`<vm>-public-ip`), attaches it to the VM and adds the firewall rule `pae-allow-public-http`
(tcp 80 from anywhere, that VM only). SSH stays IAP-only. `PUBLIC_HTTP=false` (prod's default)
removes all three. There is no login in the app yet, so a public environment is usable by anyone.

## dev (`env=dev`)

The same script with `env=dev` builds the same setup in `pae-development`: VM `pae-dev` (e2-medium),
data disk `pae-dev-data` (30 GB), service account `pae-dev-vm`, its own network, NAT, snapshot
schedule, secrets (its own random passwords and its own API keys) and `gs://pae-development-backups`.
It creates no registry and no WIF: `pae-dev-vm` gets read access to prod's registry, so dev runs the
exact images prod will. The dev VM cannot read prod's secrets or backups.

## After the first run (owner)

1. **API keys** (typed into the terminal, never committed):
   ```sh
   gcloud secrets versions add intelli-gateway-anthropic-api-key --project pae-platform-prod --data-file=-
   gcloud secrets versions add intelli-gateway-open-meteo-api-key --project pae-platform-prod --data-file=-
   ```
   (Paste the value, press Enter, then Ctrl+D; on Windows PowerShell pipe it: `"value" | gcloud ...`.)
2. **GitHub repository variables** (Settings → Secrets and variables → Actions → Variables; they
   are identifiers, not secrets): `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_CI_SERVICE_ACCOUNT`,
   printed at the end of the run.

## Change or remove

- Bigger VM: `gcloud compute instances stop pae-prod`, `set-machine-type --machine-type e2-standard-4`, start.
- Bigger data disk (online, can't shrink): `gcloud compute disks resize pae-prod-data --size 100GB`, then `resize2fs` on the VM.
- Tear down: `make prod-destroy CONFIRM=prod` (Stage 8). Until it exists, remove deletion protection
  (`gcloud compute instances update pae-prod --no-deletion-protection`) before deleting the VM.
