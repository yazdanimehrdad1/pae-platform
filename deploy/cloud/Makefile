# Cloud environment targets (run from the repo root as `make <target> env=prod|dev`; the root
# Makefile delegates here). dev is a smaller mirror of prod with non-client data; local is the
# laptop's `make up`. The laptop needs only gcloud (logged in as an owner of both projects) and
# Git Bash. Plan: deploy/PLAN.md.

# Shell: POSIX sh everywhere (Git for Windows' sh on Windows; 8.3 path, no spaces).
ifeq ($(OS),Windows_NT)
GIT_SH ?= $(firstword $(wildcard C:/PROGRA~1/Git/bin/sh.exe C:/PROGRA~1/Git/usr/bin/sh.exe $(LOCALAPPDATA)/Programs/Git/bin/sh.exe))
ifeq ($(GIT_SH),)
$(error Git for Windows sh.exe not found; pass GIT_SH=<path to sh.exe>)
endif
SHELL := $(GIT_SH)
endif
# The root Makefile turns Git-Bash path conversion off for Docker; gcloud on Windows needs it on
# (with it off, gcloud's launcher can't find its own gcloud.py).
unexport MSYS_NO_PATHCONV MSYS2_ARG_CONV_EXCL
.SHELLFLAGS := -ec

# Every target names its environment: there is no default, so nothing hits prod by accident.
ifeq ($(env),prod)
PROJECT := pae-platform-prod
VM := pae-prod
else ifeq ($(env),dev)
PROJECT := pae-development
VM := pae-dev
endif
ZONE ?= us-central1-a
UI_PORT ?= 8080
REPO_ROOT := $(abspath $(CURDIR)/../..)

GCLOUD_VM := --project $(PROJECT) --zone $(ZONE) --tunnel-through-iap --quiet --strict-host-key-checking=no
SSH := gcloud compute ssh $(VM) $(GCLOUD_VM) --command
COMPOSE_ON_VM := sudo docker compose -p pae

.PHONY: require-env infra-up ssh ui host-setup deploy status logs stats backup seed-site

require-env:
	@case "$(env)" in prod|dev) ;; *) echo "pass env=prod or env=dev" >&2; exit 2 ;; esac

# Create or complete the environment's GCP infrastructure (idempotent).
infra-up: require-env
	ENV=$(env) bash "$(REPO_ROOT)/deploy/infra/gcp/bootstrap.sh"

# A shell on the VM through IAP (OS Login; no external IP, no keys to manage).
ssh: require-env
	gcloud compute ssh $(VM) --project $(PROJECT) --zone $(ZONE) --tunnel-through-iap

# The UI through an IAP tunnel: http://localhost:$(UI_PORT) (Ctrl+C to close).
ui: require-env
	@echo "$(env) UI on http://localhost:$(UI_PORT) (Ctrl+C to stop)"
	gcloud compute start-iap-tunnel $(VM) 80 --local-host-port=localhost:$(UI_PORT) --project $(PROJECT) --zone $(ZONE)

# Copy local files to a fresh directory in the SSH user's home on the VM (relative path; each user
# - the owner, the CI account - has its own, so nobody trips over another's files in /tmp):
# $(call upload,<dir under home>,<local paths>)
upload = $(SSH) "rm -rf $(1) && mkdir -p $(1)" && gcloud compute scp --recurse $(2) $(VM):$(1)/ $(GCLOUD_VM)

# One-time (re-runnable) VM setup: data disk, Docker, registry login, Ops Agent, backup timer.
host-setup: require-env
	$(call upload,pae-setup,scripts)
	$(SSH) "sudo bash pae-setup/scripts/host-setup.sh"

# Deploy a release (default: the newest commit on origin/main, whose images CI pushed).
deploy: require-env
	@release="$(RELEASE)"; \
	if [ -z "$$release" ]; then git fetch -q origin main && release="$$(git rev-parse origin/main)"; fi; \
	echo "deploying $$release to $(env)"; \
	$(call upload,pae-bundle,compose.yaml config scripts) && \
	$(SSH) "sudo bash pae-bundle/scripts/deploy.sh $(env) $$release"

# What runs, and which release.
status: require-env
	$(SSH) "echo release=\$$(cat /opt/pae/RELEASE 2>/dev/null || echo none); $(COMPOSE_ON_VM) ps"

# The last 200 log lines (svc=<compose service> for one).
logs: require-env
	$(SSH) "$(COMPOSE_ON_VM) logs --tail 200 $(svc)"

# Live CPU and memory per container (one sample).
stats: require-env
	$(SSH) "sudo docker stats --no-stream"

# Dump every database to the environment's backup bucket now.
backup: require-env
	$(SSH) "sudo /opt/pae/scripts/backup.sh manual"

# dev only: load a powerflow simulated site into dev's backend-ot and run it in dev's powerflow.
# BUNDLE is the directory `make -C services/backend-ot seed-bundle` filled (the root
# `make cloud-seed-site env=dev SITE=...` does both). Never prod: prod holds real client data.
seed-site: require-env
	@test "$(env)" = dev || { echo "seed-site loads simulated data into dev only" >&2; exit 2; }
	@test -n "$(SITE)" && test -d "$(BUNDLE)" || { echo "usage: make seed-site env=dev SITE=<site> BUNDLE=<dir>" >&2; exit 2; }
	@echo "$(SITE)" | grep -Eqx '[a-z0-9_]+' || { echo "SITE must match [a-z0-9_]+" >&2; exit 2; }
	$(call upload,pae-seed,$(BUNDLE))
	@# docker cp leaves root-owned files the container's user can't remove, so each run gets a new
	@# directory inside the container (gone when the container is next recreated).
	$(SSH) "set -e; c=\"$(COMPOSE_ON_VM)\"; d=/tmp/pae-seed-\$$(date +%s); \
		\$$c cp pae-seed/$(notdir $(BUNDLE)) backend-ot:\$$d; \
		\$$c exec -T backend-ot sh \$$d/run_in_container.sh $(SITE); \
		curl -fsS -o /dev/null -X POST http://localhost/powerflow-api/sim/stop; \
		curl -fsS -o /dev/null -X POST http://localhost/powerflow-api/sites/$(SITE)/activate; \
		curl -fsS -o /dev/null -X POST http://localhost/powerflow-api/sim/start; \
		echo 'dev: powerflow is running $(SITE); backend-ot polls it at powerflow:502'"
