#!/usr/bin/env bash
# Deploy one release (one git SHA for every image) of the cloud stack, as root on the VM:
#   deploy.sh <env> <release-sha>
# Called by `make deploy env=...` (and later by CI's deploy workflow) after the release bundle
# (compose.yaml, config/, scripts/) has been copied next to this script.
#
# 1. checks the environment matches this VM's project (dev config never lands on prod);
# 2. keeps the bundle in /opt/pae/releases/<sha>/ (rollback reuses it);
# 3. writes each service's env file from Secret Manager into /opt/pae/env/ (root, 0600) -- values
#    are never printed;
# 4. backs up the databases when the stack is running, pulls the images, runs the migrations,
#    starts everything and waits until every container is healthy;
# 5. checks the stack through the UI's origin, then records the release (the previous one in
#    RELEASE.prev). On failure it redeploys the previous release and exits non-zero.
set -euo pipefail

env_name="${1:-}"
release="${2:-}"
mode="${3:-}" # internal: "rollback" when redeploying the previous release

case "$env_name" in dev | prod) ;; *) echo "usage: deploy.sh dev|prod <release-sha>" >&2; exit 2 ;; esac
[[ "$release" =~ ^[0-9a-f]{40}$ ]] || { echo "release must be a full 40-character git SHA" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)" >&2; exit 1; }

PAE_DIR="/opt/pae"
DATA_MOUNT="/mnt/pae-data"
REGISTRY="us-central1-docker.pkg.dev/pae-platform-prod/pae"
bundle="$(cd "$(dirname "$0")/.." && pwd)"
release_dir="${PAE_DIR}/releases/${release}"

log() { printf '[deploy %s %s] %s\n' "$env_name" "${release:0:12}" "$*"; }

# ---- 1. right VM for this environment ----------------------------------------------------
# shellcheck disable=SC1090,SC2153 # PROJECT is set by the sourced config file
project="$(. "${bundle}/config/${env_name}.env" && echo "$PROJECT")"
vm_project="$(curl -fsS -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/project/project-id)"
if [ "$project" != "$vm_project" ]; then
	echo "this VM is in ${vm_project}, but config/${env_name}.env is for ${project}: refusing" >&2
	exit 1
fi
mountpoint -q "$DATA_MOUNT" || { echo "${DATA_MOUNT} is not mounted: run make host-setup env=${env_name}" >&2; exit 1; }

# ---- 2. keep the bundle --------------------------------------------------------------------
if [ "$bundle" != "$release_dir" ]; then
	rm -rf "$release_dir"
	mkdir -p "$release_dir"
	cp -r "${bundle}/compose.yaml" "${bundle}/config" "${bundle}/scripts" "$release_dir/"
fi
cd "$release_dir"
printf 'REGISTRY=%s\nRELEASE=%s\n' "$REGISTRY" "$release" >release.env
compose=(docker compose --project-directory "$release_dir" -f compose.yaml
	--env-file "config/${env_name}.env" --env-file release.env)

# ---- 3. secrets -> env files -----------------------------------------------------------------
secret() { # secret <name> [optional]: the latest value, or "" for an optional secret with no version
	local value error_file
	error_file="$(mktemp)"
	if ! value="$(gcloud secrets versions access latest --secret "$1" --project "$project" 2>"$error_file")"; then
		# Only "no version yet" counts as empty for an optional secret; anything else (permission,
		# a missing secret, an API error) fails the deploy. The error text never holds the value.
		if [ "${2:-}" = optional ] && grep -q "NOT_FOUND" "$error_file" && grep -qi "version" "$error_file"; then
			rm -f "$error_file"
			return 0
		fi
		echo "secret $1 in ${project}: $(tr -d '\r' <"$error_file" | head -c 300)" >&2
		rm -f "$error_file"
		return 1
	fi
	rm -f "$error_file"
	printf '%s' "$value" | tr -d '\r\n'
}
umask 077
mkdir -p "${PAE_DIR}/env"
log "writing env files from Secret Manager (${project})"
backend_pw="$(secret backend-ot-postgres-password)"
gateway_pw="$(secret intelli-gateway-postgres-password)"
powerflow_pw="$(secret powerflow-postgres-password)"
anthropic_key="$(secret intelli-gateway-anthropic-api-key optional)"
open_meteo_key="$(secret intelli-gateway-open-meteo-api-key optional)"
printf 'POSTGRES_PASSWORD=%s\n' "$backend_pw" >"${PAE_DIR}/env/backend-ot-postgres.env"
printf 'POSTGRES_PASSWORD=%s\n' "$backend_pw" >"${PAE_DIR}/env/backend-ot.env"
printf 'POSTGRES_PASSWORD=%s\n' "$gateway_pw" >"${PAE_DIR}/env/intelli-gateway-postgres.env"
{
	printf 'DATABASE_URL=postgresql+asyncpg://intelli_gateway:%s@intelli-gateway-postgres:5432/intelli_gateway\n' "$gateway_pw"
	[ -n "$anthropic_key" ] && printf 'ANTHROPIC_API_KEY=%s\n' "$anthropic_key"
	[ -n "$open_meteo_key" ] && printf 'OPEN_METEO_API_KEY=%s\n' "$open_meteo_key"
	true
} >"${PAE_DIR}/env/intelli-gateway.env"
printf 'POSTGRES_PASSWORD=%s\n' "$powerflow_pw" >"${PAE_DIR}/env/powerflow-postgres.env"
printf 'DATABASE_URL=postgresql+asyncpg://powerflow:%s@powerflow-postgres:5432/powerflow\n' "$powerflow_pw" >"${PAE_DIR}/env/powerflow.env"
unset backend_pw gateway_pw powerflow_pw anthropic_key open_meteo_key
[ -s "${PAE_DIR}/env/intelli-gateway.env" ] && ! grep -q '^ANTHROPIC_API_KEY=' "${PAE_DIR}/env/intelli-gateway.env" &&
	log "note: intelli-gateway-anthropic-api-key has no value yet; the assistant answers 503 until it does"
umask 022

# ---- 4. backup, pull, migrate, start -----------------------------------------------------------
for volume in backend-ot-postgres-data intelli-gateway-postgres-data powerflow-postgres-data powerflow-profiles; do
	mkdir -p "${DATA_MOUNT}/volumes/${volume}"
done
if [ -n "$(docker ps -q --filter label=com.docker.compose.project=pae)" ]; then
	log "pre-deploy backup"
	bash "${release_dir}/scripts/backup.sh" pre-deploy
fi

deploy_failed() {
	log "FAILED: $1"
	"${compose[@]}" ps -a || true
	previous="$(cat "${PAE_DIR}/RELEASE" 2>/dev/null || true)"
	if [ "$mode" != rollback ] && [ -n "$previous" ] && [ "$previous" != "$release" ] && [ -d "${PAE_DIR}/releases/${previous}" ]; then
		log "rolling back to ${previous:0:12}"
		bash "${PAE_DIR}/releases/${previous}/scripts/deploy.sh" "$env_name" "$previous" rollback || true
	fi
	exit 1
}

log "pulling images"
"${compose[@]}" --profile migrate pull --quiet || deploy_failed "image pull"
log "migrating backend-ot"
"${compose[@]}" run --rm backend-ot-migrate || deploy_failed "backend-ot migrations"
log "starting the stack"
"${compose[@]}" up -d --wait --wait-timeout 300 --remove-orphans || deploy_failed "containers not healthy"

# ---- 5. check through the UI origin, record ------------------------------------------------------
for path in / /api/readyz /intelli-gateway-api/readyz /powerflow-api/health; do
	code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost${path}")"
	[ "$code" = 200 ] || deploy_failed "GET ${path} answered ${code}"
	log "GET ${path} -> 200"
done
current="$(cat "${PAE_DIR}/RELEASE" 2>/dev/null || true)"
if [ -n "$current" ] && [ "$current" != "$release" ]; then
	echo "$current" >"${PAE_DIR}/RELEASE.prev"
fi
echo "$release" >"${PAE_DIR}/RELEASE"
log "deployed"
