#!/usr/bin/env bash
# One-time (and re-runnable) setup of a cloud VM, run as root on the VM by `make host-setup env=...`:
# - formats the data disk once and mounts it at /mnt/pae-data (by UUID, nofail);
# - installs Docker Engine + the compose plugin from Docker's apt repository;
# - lets root's Docker pull from Artifact Registry with the VM's service account;
# - installs the Google Cloud Ops Agent and ships the containers' logs to Cloud Logging;
# - installs the weekly database backup timer (scripts/backup.sh).
# Idempotent: every step checks before it changes anything.
set -euo pipefail

REGISTRY_HOST="us-central1-docker.pkg.dev"
DATA_DEVICE="/dev/disk/by-id/google-pae-data"
DATA_MOUNT="/mnt/pae-data"
PAE_DIR="/opt/pae"

step() { printf '\n==> %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)" >&2; exit 1; }
script_dir="$(cd "$(dirname "$0")" && pwd)"

step "Data disk ${DATA_DEVICE} -> ${DATA_MOUNT}"
if ! blkid "$DATA_DEVICE" >/dev/null 2>&1; then
	echo "    formatting (first use)"
	mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard "$DATA_DEVICE"
fi
uuid="$(blkid -s UUID -o value "$DATA_DEVICE")"
mkdir -p "$DATA_MOUNT"
if ! grep -q "UUID=${uuid}" /etc/fstab; then
	echo "UUID=${uuid} ${DATA_MOUNT} ext4 discard,defaults,nofail 0 2" >>/etc/fstab
fi
mountpoint -q "$DATA_MOUNT" || mount "$DATA_MOUNT"
mkdir -p "${DATA_MOUNT}/volumes"
df -h "$DATA_MOUNT" | tail -1

step "Docker Engine + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
	apt-get update -q
	apt-get install -y -q ca-certificates curl gnupg
	install -m 0755 -d /etc/apt/keyrings
	curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
	chmod a+r /etc/apt/keyrings/docker.asc
	# shellcheck disable=SC1091
	codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${codename} stable" \
		>/etc/apt/sources.list.d/docker.list
	apt-get update -q
	apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
systemctl enable --now docker >/dev/null
docker --version
docker compose version

step "Artifact Registry login for root (the VM's service account, no key)"
gcloud auth configure-docker "$REGISTRY_HOST" --quiet >/dev/null
echo "    ${REGISTRY_HOST} uses the gcloud credential helper"

step "Google Cloud Ops Agent (metrics + container logs)"
if ! systemctl list-unit-files google-cloud-ops-agent.service >/dev/null 2>&1 ||
	! systemctl is-enabled google-cloud-ops-agent >/dev/null 2>&1; then
	curl -fsSL https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh -o /tmp/add-ops-agent-repo.sh
	bash /tmp/add-ops-agent-repo.sh --also-install
fi
install -m 0644 "${script_dir}/ops-agent.yaml" /etc/google-cloud-ops-agent/config.yaml
systemctl restart google-cloud-ops-agent
systemctl is-active google-cloud-ops-agent

step "Weekly database backups (Sunday 04:00 UTC)"
mkdir -p "${PAE_DIR}/scripts"
install -m 0755 "${script_dir}/backup.sh" "${PAE_DIR}/scripts/backup.sh"
cat >/etc/systemd/system/pae-backup.service <<'UNIT'
[Unit]
Description=PAE weekly database backup to GCS
After=docker.service
[Service]
Type=oneshot
ExecStart=/opt/pae/scripts/backup.sh weekly
UNIT
cat >/etc/systemd/system/pae-backup.timer <<'UNIT'
[Unit]
Description=PAE weekly database backup
[Timer]
OnCalendar=Sun *-*-* 04:00:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now pae-backup.timer >/dev/null
systemctl list-timers pae-backup.timer --no-pager --no-legend

step "Done"
