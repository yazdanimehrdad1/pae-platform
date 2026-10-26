#!/usr/bin/env bash
# Create (or complete) the production infrastructure in GCP. Idempotent: every step checks first and
# only creates what is missing, so re-running it is safe and changes nothing once it is all there.
#
#   make infra-up env=prod             (or: ENV=prod bash deploy/infra/gcp/bootstrap.sh)
#   make infra-up env=dev
#
# Two environments, same shape: prod (pae-platform-prod, real sites) and dev (pae-development, a
# smaller mirror with non-client data). The image registry and the GitHub Workload Identity
# Federation live in prod only; dev's VM pulls the same images from there.
#
# Needs only gcloud, logged in as an owner of both projects (gcloud auth login). It never prints a
# secret: database passwords are generated with openssl and piped straight into Secret Manager; the
# API keys are created empty and the owner adds their values (see README.md).
#
# What it creates is listed in README.md. Settings can be overridden with environment variables.
set -euo pipefail

ENV="${ENV:-}"
case "$ENV" in
prod)
	PROJECT="${PROJECT:-pae-platform-prod}"
	VM="pae-prod"
	MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-2}"
	DATA_DISK_GB="${DATA_DISK_GB:-50}"
	PUBLIC_HTTP="${PUBLIC_HTTP:-false}"
	;;
dev)
	PROJECT="${PROJECT:-pae-development}"
	VM="pae-dev"
	MACHINE_TYPE="${MACHINE_TYPE:-e2-medium}"
	DATA_DISK_GB="${DATA_DISK_GB:-30}"
	# Temporary (2026-10-26): dev is public over plain HTTP for demos, linked from the owner's
	# website. No login exists yet (deploy/PLAN.md, Stage 4); dev holds simulated data only.
	PUBLIC_HTTP="${PUBLIC_HTTP:-true}"
	;;
*)
	echo "usage: ENV=prod|dev bash deploy/infra/gcp/bootstrap.sh   (make infra-up env=prod|dev)" >&2
	exit 2
	;;
esac
# The shared registry and WIF are in the prod project, whichever environment this run is for.
REGISTRY_PROJECT="${REGISTRY_PROJECT:-pae-platform-prod}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
BACKUP_REGION="${BACKUP_REGION:-us-east1}"
GITHUB_REPO="${GITHUB_REPO:-yazdanimehrdad1/pae-platform}"
# GitHub's numeric ids (https://api.github.com/repos/<owner>/<repo>): unlike names, they can't be
# re-registered by someone else after a rename or delete, so WIF trusts these.
GITHUB_REPO_ID="${GITHUB_REPO_ID:-1384254484}"
GITHUB_OWNER_ID="${GITHUB_OWNER_ID:-11001227}"

BOOT_DISK_GB="${BOOT_DISK_GB:-20}"
DATA_DISK="${VM}-data"
NETWORK="pae-vpc"
SUBNET="pae-usc1"
SUBNET_RANGE="10.10.0.0/24"
NETWORK_TAG="$VM"
IAP_RANGE="35.235.240.0/20" # Google's IAP TCP forwarding source range
REGISTRY_REPO="pae"
BACKUP_BUCKET="${PROJECT}-backups"
SNAPSHOT_POLICY="pae-daily"
VM_SA="${VM}-vm"
CI_SA="pae-ci"
WIF_POOL="github"
WIF_PROVIDER="github-actions"

VM_SA_EMAIL="${VM_SA}@${PROJECT}.iam.gserviceaccount.com"
CI_SA_EMAIL="${CI_SA}@${REGISTRY_PROJECT}.iam.gserviceaccount.com"

# Secrets: generated ones get a random value once; owner ones are created empty.
GENERATED_SECRETS=(backend-ot-postgres-password intelli-gateway-postgres-password powerflow-postgres-password)
OWNER_SECRETS=(intelli-gateway-anthropic-api-key intelli-gateway-open-meteo-api-key)

gc() { gcloud --project "$PROJECT" --quiet "$@"; }
# A gcloud value to use in the script: on Windows gcloud ends its lines with CRLF, so drop the CR.
gcv() { gc "$@" | tr -d '\r'; }
exists() { "$@" >/dev/null 2>&1; }
step() { printf '\n==> %s\n' "$*"; }
skip() { printf '    exists: %s\n' "$*"; }

step "Project ${PROJECT}"
if ! exists gcloud projects describe "$PROJECT"; then
	echo "Project ${PROJECT} not found (create it and link billing first; see README.md)." >&2
	exit 1
fi
PROJECT_NUMBER="$(gcv projects describe "$PROJECT" --format='value(projectNumber)')"

step "APIs"
gc services enable compute.googleapis.com iap.googleapis.com artifactregistry.googleapis.com \
	secretmanager.googleapis.com iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
	cloudresourcemanager.googleapis.com logging.googleapis.com monitoring.googleapis.com

step "Remove the auto-created 'default' network (its rules open SSH/RDP to the internet)"
if exists gc compute networks describe default; then
	if [ -n "$(gcv compute instances list --filter 'networkInterfaces.network~/networks/default$' --format 'value(name)')" ]; then
		echo "    kept: VMs still use the default network" >&2
	else
		for rule in $(gcv compute firewall-rules list --filter 'network~/networks/default$' --format 'value(name)'); do
			gc compute firewall-rules delete "$rule"
		done
		gc compute networks delete default
	fi
else
	skip "no default network"
fi

step "Network ${NETWORK} / ${SUBNET} (private Google access on), firewall from IAP only"
if exists gc compute networks describe "$NETWORK"; then skip "$NETWORK"; else
	gc compute networks create "$NETWORK" --subnet-mode=custom
fi
if exists gc compute networks subnets describe "$SUBNET" --region "$REGION"; then skip "$SUBNET"; else
	gc compute networks subnets create "$SUBNET" --network "$NETWORK" --region "$REGION" \
		--range "$SUBNET_RANGE" --enable-private-ip-google-access
fi
if exists gc compute firewall-rules describe pae-allow-iap; then skip pae-allow-iap; else
	gc compute firewall-rules create pae-allow-iap --network "$NETWORK" --direction INGRESS \
		--action ALLOW --rules tcp:22,tcp:80 --source-ranges "$IAP_RANGE" --target-tags "$NETWORK_TAG" \
		--description "SSH and the UI through IAP TCP forwarding only"
fi

step "Cloud NAT (outbound internet for a VM without an external IP)"
if exists gc compute routers describe pae-router --region "$REGION"; then skip pae-router; else
	gc compute routers create pae-router --network "$NETWORK" --region "$REGION"
fi
if exists gc compute routers nats describe pae-nat --router pae-router --region "$REGION"; then skip pae-nat; else
	gc compute routers nats create pae-nat --router pae-router --region "$REGION" \
		--auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges
fi

step "Service accounts"
accounts=("$VM_SA:PAE ${ENV} VM")
[ "$ENV" = prod ] && accounts+=("$CI_SA:PAE CI (GitHub Actions via WIF)")
for account in "${accounts[@]}"; do
	name="${account%%:*}"
	if exists gc iam service-accounts describe "${name}@${PROJECT}.iam.gserviceaccount.com"; then skip "$name"; else
		gc iam service-accounts create "$name" --display-name "${account#*:}"
	fi
done
for role in roles/logging.logWriter roles/monitoring.metricWriter; do
	gc projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:${VM_SA_EMAIL}" \
		--role "$role" --condition=None >/dev/null
done

if [ "$ENV" = prod ]; then
step "Artifact Registry ${REGISTRY_REPO} (keeps the 30 newest releases per image)"
if exists gc artifacts repositories describe "$REGISTRY_REPO" --location "$REGION"; then skip "$REGISTRY_REPO"; else
	gc artifacts repositories create "$REGISTRY_REPO" --repository-format docker --location "$REGION" \
		--description "PAE production images: pae-<service>:<git sha>"
fi
policy_file="$(mktemp)"
trap 'rm -f "$policy_file"' EXIT
cat >"$policy_file" <<'POLICY'
[
  {"name": "keep-newest-30", "action": {"type": "Keep"},
   "mostRecentVersions": {"keepCount": 30}},
  {"name": "delete-older", "action": {"type": "Delete"},
   "condition": {"tagState": "any", "olderThan": "2592000s"}}
]
POLICY
gc artifacts repositories set-cleanup-policies "$REGISTRY_REPO" --location "$REGION" \
	--policy "$policy_file" --no-dry-run >/dev/null
gc artifacts repositories add-iam-policy-binding "$REGISTRY_REPO" --location "$REGION" \
	--member "serviceAccount:${CI_SA_EMAIL}" --role roles/artifactregistry.writer >/dev/null
fi

step "Image pulls: ${VM_SA} reads ${REGISTRY_PROJECT}'s registry (one image, both environments)"
gcloud --project "$REGISTRY_PROJECT" --quiet artifacts repositories add-iam-policy-binding "$REGISTRY_REPO" \
	--location "$REGION" --member "serviceAccount:${VM_SA_EMAIL}" --role roles/artifactregistry.reader >/dev/null

step "Backup bucket gs://${BACKUP_BUCKET} (${BACKUP_REGION}, private)"
if exists gc storage buckets describe "gs://${BACKUP_BUCKET}"; then skip "$BACKUP_BUCKET"; else
	gc storage buckets create "gs://${BACKUP_BUCKET}" --location "$BACKUP_REGION" \
		--uniform-bucket-level-access --public-access-prevention
fi
gc storage buckets add-iam-policy-binding "gs://${BACKUP_BUCKET}" \
	--member "serviceAccount:${VM_SA_EMAIL}" --role roles/storage.objectAdmin >/dev/null

step "Secret Manager"
for secret in "${GENERATED_SECRETS[@]}"; do
	if exists gc secrets describe "$secret"; then skip "$secret"; else
		openssl rand -base64 48 | tr -d '\n/+=' | head -c 40 |
			gc secrets create "$secret" --replication-policy automatic --data-file=- >/dev/null
		echo "    created $secret (random value, never shown)"
	fi
done
for secret in "${OWNER_SECRETS[@]}"; do
	if exists gc secrets describe "$secret"; then skip "$secret"; else
		gc secrets create "$secret" --replication-policy automatic >/dev/null
		echo "    created $secret (empty: the owner adds its value)"
	fi
done
for secret in "${GENERATED_SECRETS[@]}" "${OWNER_SECRETS[@]}"; do
	gc secrets add-iam-policy-binding "$secret" --member "serviceAccount:${VM_SA_EMAIL}" \
		--role roles/secretmanager.secretAccessor >/dev/null
done

if [ "$ENV" = prod ]; then
step "Workload Identity Federation for ${GITHUB_REPO} (main branch only)"
if exists gc iam workload-identity-pools describe "$WIF_POOL" --location global; then skip "$WIF_POOL"; else
	gc iam workload-identity-pools create "$WIF_POOL" --location global --display-name "GitHub Actions"
fi
# Trust only this repository (by numeric id and owner id) on refs/heads/main. The provider is
# created or, when it exists, updated, so a re-run also repairs a drifted condition.
WIF_MAPPING="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref"
WIF_CONDITION="assertion.repository_id == '${GITHUB_REPO_ID}' && assertion.repository_owner_id == '${GITHUB_OWNER_ID}' && assertion.ref == 'refs/heads/main'"
if exists gc iam workload-identity-pools providers describe "$WIF_PROVIDER" --workload-identity-pool "$WIF_POOL" --location global; then
	gc iam workload-identity-pools providers update-oidc "$WIF_PROVIDER" --location global \
		--workload-identity-pool "$WIF_POOL" --attribute-mapping "$WIF_MAPPING" \
		--attribute-condition "$WIF_CONDITION" >/dev/null
	echo "    updated: ${WIF_PROVIDER} (mapping and condition)"
else
	gc iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" --location global \
		--workload-identity-pool "$WIF_POOL" --display-name "pae-platform" \
		--issuer-uri "https://token.actions.githubusercontent.com" \
		--attribute-mapping "$WIF_MAPPING" --attribute-condition "$WIF_CONDITION"
fi
WIF_PRINCIPALS="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}"
# An older version of this script bound by repository name; that binding is removed.
gc iam service-accounts remove-iam-policy-binding "$CI_SA_EMAIL" --role roles/iam.workloadIdentityUser \
	--member "${WIF_PRINCIPALS}/attribute.repository/${GITHUB_REPO}" >/dev/null 2>&1 || true
# A just-created service account can take a few seconds to propagate before its policy can be set.
for attempt in 1 2 3 4 5 6; do
	if gc iam service-accounts add-iam-policy-binding "$CI_SA_EMAIL" --role roles/iam.workloadIdentityUser \
		--member "${WIF_PRINCIPALS}/attribute.repository_id/${GITHUB_REPO_ID}" >/dev/null; then
		break
	fi
	[ "$attempt" -lt 6 ] || exit 1
	echo "    retrying in 10 s (new service account still propagating)"
	sleep 10
done
fi

step "CD access: ${CI_SA} may SSH (through IAP, OS Login with sudo) to ${VM} to run deploy.sh"
# Project-level because the roles are about reaching this project's one VM; IAP's firewall rule
# and the VM's lack of an external IP still apply. serviceAccountUser is needed to log in to a VM
# that runs as ${VM_SA}.
for role in roles/iap.tunnelResourceAccessor roles/compute.osAdminLogin roles/compute.viewer; do
	gc projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:${CI_SA_EMAIL}" \
		--role "$role" --condition=None >/dev/null
done
gc iam service-accounts add-iam-policy-binding "$VM_SA_EMAIL" --role roles/iam.serviceAccountUser \
	--member "serviceAccount:${CI_SA_EMAIL}" >/dev/null

step "Daily snapshot schedule ${SNAPSHOT_POLICY} (7 kept)"
if exists gc compute resource-policies describe "$SNAPSHOT_POLICY" --region "$REGION"; then skip "$SNAPSHOT_POLICY"; else
	gc compute resource-policies create snapshot-schedule "$SNAPSHOT_POLICY" --region "$REGION" \
		--daily-schedule --start-time 03:00 --max-retention-days 7 \
		--on-source-disk-delete keep-auto-snapshots --storage-location "$REGION"
fi

step "Data disk ${DATA_DISK} (${DATA_DISK_GB} GB pd-balanced)"
if exists gc compute disks describe "$DATA_DISK" --zone "$ZONE"; then skip "$DATA_DISK"; else
	gc compute disks create "$DATA_DISK" --zone "$ZONE" --size "${DATA_DISK_GB}GB" --type pd-balanced \
		--resource-policies "$SNAPSHOT_POLICY"
fi

step "VM ${VM} (${MACHINE_TYPE}, Debian 12, no external IP)"
if exists gc compute instances describe "$VM" --zone "$ZONE"; then skip "$VM"; else
	gc compute instances create "$VM" --zone "$ZONE" --machine-type "$MACHINE_TYPE" \
		--network-interface "subnet=${SUBNET},no-address" \
		--image-family debian-12 --image-project debian-cloud \
		--boot-disk-size "${BOOT_DISK_GB}GB" --boot-disk-type pd-balanced --boot-disk-device-name "$VM" \
		--disk "name=${DATA_DISK},device-name=pae-data,mode=rw,boot=no,auto-delete=no" \
		--service-account "$VM_SA_EMAIL" --scopes cloud-platform \
		--tags "$NETWORK_TAG" --metadata enable-oslogin=TRUE \
		--shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring \
		--deletion-protection
fi
PUBLIC_IP_NAME="${VM}-public-ip"
if [ "$PUBLIC_HTTP" = true ]; then
	step "Public HTTP (port 80 from the internet) on a static IP"
	if exists gc compute addresses describe "$PUBLIC_IP_NAME" --region "$REGION"; then skip "$PUBLIC_IP_NAME"; else
		gc compute addresses create "$PUBLIC_IP_NAME" --region "$REGION" --network-tier PREMIUM
	fi
	public_ip="$(gcv compute addresses describe "$PUBLIC_IP_NAME" --region "$REGION" --format 'value(address)')"
	if [ "$(gcv compute instances describe "$VM" --zone "$ZONE" --format 'value(networkInterfaces[0].accessConfigs[0].natIP)')" = "$public_ip" ]; then
		skip "${public_ip} on ${VM}"
	else
		gc compute instances add-access-config "$VM" --zone "$ZONE" --access-config-name external-nat --address "$public_ip"
	fi
	if exists gc compute firewall-rules describe pae-allow-public-http; then skip pae-allow-public-http; else
		gc compute firewall-rules create pae-allow-public-http --network "$NETWORK" --direction INGRESS \
			--action ALLOW --rules tcp:80 --source-ranges 0.0.0.0/0 --target-tags "$NETWORK_TAG" \
			--description "Public HTTP for demos (no login yet); SSH stays IAP-only"
	fi
	echo "    public UI: http://${public_ip}"
else
	step "No public access (IAP only)"
	if exists gc compute firewall-rules describe pae-allow-public-http; then
		gc compute firewall-rules delete pae-allow-public-http
	fi
	if [ -n "$(gcv compute instances describe "$VM" --zone "$ZONE" --format 'value(networkInterfaces[0].accessConfigs[0].natIP)')" ]; then
		gc compute instances delete-access-config "$VM" --zone "$ZONE" --access-config-name external-nat
	fi
	if exists gc compute addresses describe "$PUBLIC_IP_NAME" --region "$REGION"; then
		gc compute addresses delete "$PUBLIC_IP_NAME" --region "$REGION"
	fi
fi

for disk in "$VM" "$DATA_DISK"; do
	if gcv compute disks describe "$disk" --zone "$ZONE" --format 'value(resourcePolicies)' | grep -q "/${SNAPSHOT_POLICY}"; then
		skip "snapshot schedule on ${disk}"
	else
		gc compute disks add-resource-policies "$disk" --zone "$ZONE" --resource-policies "$SNAPSHOT_POLICY"
	fi
done

step "Done (${ENV})"
cat <<SUMMARY
    VM:            ${VM} (${PROJECT}, ${ZONE}), reach it with: make ssh env=${ENV}
    Images from:   ${REGION}-docker.pkg.dev/${REGISTRY_PROJECT}/${REGISTRY_REPO}
    Backup bucket: gs://${BACKUP_BUCKET}

    API keys to add (values typed by the owner, never committed):
      gcloud secrets versions add intelli-gateway-anthropic-api-key --project ${PROJECT} --data-file=-
      gcloud secrets versions add intelli-gateway-open-meteo-api-key --project ${PROJECT} --data-file=-
SUMMARY
if [ "$ENV" = prod ]; then
	cat <<SUMMARY

    GitHub repository variables (Settings > Secrets and variables > Actions > Variables), not secrets:
      GCP_WORKLOAD_IDENTITY_PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}
      GCP_CI_SERVICE_ACCOUNT         = ${CI_SA_EMAIL}
SUMMARY
fi
