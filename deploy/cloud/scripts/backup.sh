#!/usr/bin/env bash
# Dump each database of the running stack to this environment's backup bucket:
#   gs://<project>-backups/<label>/<UTC timestamp>/<database>.dump   (pg_dump custom format)
# Run as root on the VM: weekly by the pae-backup timer (label "weekly"), before every deploy
# (label "pre-deploy", from deploy.sh), or by hand (`make backup env=...`, label "manual").
# Restore one: gcloud storage cat gs://.../<db>.dump | docker exec -i <container> pg_restore -U <user> -d <db> --clean
set -euo pipefail

label="${1:-manual}"
project="$(curl -fsS -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/project/project-id)"
bucket="gs://${project}-backups"
stamp="$(date -u +%Y-%m-%dT%H%M%SZ)"

# service:database:user, as created by deploy/cloud/compose.yaml
databases=(
	"backend-ot-postgres:pae_backend_ot:pae_backend_ot_user"
	"intelli-gateway-postgres:intelli_gateway:intelli_gateway"
	"powerflow-postgres:powerflow:powerflow"
)

container_of() {
	docker ps -q --filter "label=com.docker.compose.project=pae" --filter "label=com.docker.compose.service=$1"
}

found=0
for entry in "${databases[@]}"; do
	IFS=: read -r service database user <<<"$entry"
	container="$(container_of "$service")"
	if [ -z "$container" ]; then
		echo "backup: ${service} is not running, skipped"
		continue
	fi
	target="${bucket}/${label}/${stamp}/${database}.dump"
	docker exec "$container" pg_dump -U "$user" -d "$database" -Fc | gcloud storage cp - "$target" --quiet
	echo "backup: ${database} -> ${target}"
	found=$((found + 1))
done
echo "backup: ${found} database(s) dumped (${label})"
