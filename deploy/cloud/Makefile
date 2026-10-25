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

.PHONY: require-env infra-up ssh ui

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
