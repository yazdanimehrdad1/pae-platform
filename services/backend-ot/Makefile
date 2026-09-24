# backend-ot — service Makefile.
#
# Run from anywhere with `make -C services/backend-ot <target>` (or from this directory).
# Standard targets (same names in every service): install lint format typecheck test
# test-integration build up down logs run contract. Service-specific: migrate seed-db cloud-*.
# Tooling: uv only; every Python tool runs from uv.lock via `uv run --frozen`.

# ---------------------------------------------------------------------------
# Shell: POSIX sh everywhere. On Windows, GNU make would otherwise fall back to cmd.exe,
# so point it at Git for Windows' sh (8.3 path: make can't handle spaces in SHELL).
# Override with `make GIT_SH=/path/to/sh.exe` if Git lives elsewhere.
# ---------------------------------------------------------------------------
ifeq ($(OS),Windows_NT)
GIT_SH ?= $(firstword $(wildcard C:/PROGRA~1/Git/bin/sh.exe C:/PROGRA~1/Git/usr/bin/sh.exe $(LOCALAPPDATA)/Programs/Git/bin/sh.exe))
ifeq ($(GIT_SH),)
$(error Git for Windows sh.exe not found; pass GIT_SH=<path to sh.exe>)
endif
SHELL := $(GIT_SH)
# Stop Git-Bash rewriting container paths like /app into C:/Program Files/Git/app.
export MSYS_NO_PATHCONV := 1
export MSYS2_ARG_CONV_EXCL := *
endif
.SHELLFLAGS := -ec

.DEFAULT_GOAL := help
.PHONY: help install lint lint-fix format typecheck test test-unit test-integration test-all contract \
	build rebuild up up-build down restart logs ps shell health clean \
	run migrate apply-migration seed-db cloud-down cloud-up

# Standalone stack. Host ports: BACKEND_OT_HTTP_PORT / _POSTGRES_PORT / _REDIS_PORT (defaults
# 8000/5435/6380). The Modbus aggregator defaults to mock-modbus's host port via
# host.docker.internal; override with BACKEND_OT_AGGREGATOR_HOST / _PORT.
COMPOSE := docker compose -f compose.yaml
APP     := backend-ot
HTTP_PORT := $(or $(BACKEND_OT_HTTP_PORT),8000)
UV_RUN  := uv run --frozen

# Integration-test stack: one isolated compose project per worktree, so parallel agent
# worktrees never share (or tear down) each other's throwaway postgres/redis.
WORKTREE_ID  := $(shell basename "$(abspath $(CURDIR)/../..)" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9\n' '-')
TEST_COMPOSE := docker compose -p backend-ot-test-$(WORKTREE_ID) -f compose.test.yaml

# config.py requires POSTGRES_PASSWORD at import time. Unit tests do no I/O, so any value
# works; a real value from the environment or .env still takes precedence.
UNIT_ENV := POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-unit-test} SCHEDULER_ENABLED=false

help:
	@echo "backend-ot — make -C services/backend-ot <target>"
	@echo ""
	@echo "Develop (host, via uv):"
	@echo "  install          uv sync (creates .venv from uv.lock, incl. dev group)"
	@echo "  lint / lint-fix  ruff check src tests (CI-enforced) / auto-fix"
	@echo "  format           black + ruff --fix on src/"
	@echo "  typecheck        mypy src (not yet blocking)"
	@echo "  test             unit tests (fast, no Docker). TEST_PATH=... to narrow"
	@echo "  test-integration integration tests on a throwaway postgres+redis stack (Docker)"
	@echo "  test-all         test + test-integration"
	@echo "  run              run the API on the host (needs postgres+redis reachable)"
	@echo "  migrate          apply SQL migrations from the host"
	@echo "  contract         regenerate $(CONTRACT_FILE) (the OpenAPI spec)"
	@echo ""
	@echo "Containers (docker compose):"
	@echo "  build / rebuild  build the image (rebuild = no cache)"
	@echo "  up / up-build    start postgres, redis, app (up-build builds first)"
	@echo "  down / restart / logs / ps / shell / health / clean"
	@echo "  apply-migration  run migrations inside the running app container"
	@echo "  seed-db          load dev mock data into the running stack"
	@echo ""
	@echo "Cloud cost control (GKE): cloud-down / cloud-up"

# ---------------------------------------------------------------------------
# Develop
# ---------------------------------------------------------------------------
install:
	uv sync --frozen

lint:
	$(UV_RUN) ruff check src tests

# B904 exception chaining is not auto-fixable and must be fixed by hand.
lint-fix:
	$(UV_RUN) ruff check --fix src tests

format:
	$(UV_RUN) black src
	$(UV_RUN) ruff check --fix src

# Not yet blocking: the codebase is not fully typed. Drop the `||` once `mypy src` is clean.
typecheck:
	$(UV_RUN) mypy src || echo "typecheck: mypy reported issues (not yet blocking)"

test:
	$(UNIT_ENV) $(UV_RUN) pytest $(or $(TEST_PATH),tests/unit) -v --color=yes -rfE

# Alias kept for muscle memory; `test` is the standard name.
test-unit: test

# Always tears the stack down; keeps pytest's exit code.
test-integration:
	@echo "Running integration tests (project backend-ot-test-$(WORKTREE_ID))..."
	@docker volume create backend-ot-uv-cache >/dev/null
	@status=0; PYTEST_TARGET=$(or $(TEST_PATH),tests/integration) $(TEST_COMPOSE) run --rm tests || status=$$?; \
		$(TEST_COMPOSE) down --remove-orphans >/dev/null 2>&1 || true; exit $$status

test-all: test test-integration

# Runs from src/ like the container does; config.py finds ../.env regardless of CWD.
run:
	cd src && $(UV_RUN) python -m main

migrate:
	$(UV_RUN) python scripts/migrate_db.py

# Published HTTP API (contracts/ is the only directory shared between services).
# Run after any route/model change; `make test` fails while the contract is stale.
CONTRACT_FILE := ../../contracts/openapi/backend-ot.openapi.json
contract:
	$(UNIT_ENV) $(UV_RUN) python scripts/export_openapi.py --output $(CONTRACT_FILE)

# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------
build:
	$(COMPOSE) build

rebuild:
	$(COMPOSE) build --no-cache

# --wait blocks until postgres, redis and the app report healthy (migrations run in the
# app's entrypoint before uvicorn starts).
up:
	$(COMPOSE) up -d --wait

up-build:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f $(APP)

ps:
	$(COMPOSE) ps

shell:
	$(COMPOSE) exec $(APP) /bin/bash

health:
	@curl -fsS http://localhost:$(HTTP_PORT)/api/healthz && echo || echo "Service not responding"

# Removes this project's containers and the images it built (volumes are kept).
clean:
	$(COMPOSE) down --rmi local

apply-migration:
	$(COMPOSE) exec $(APP) python scripts/migrate_db.py

# tests/ and contracts/ are not shipped in the image, so copy the seed files in first —
# including mock-modbus's register-map contract, which the seeded devices/points are built from.
MOCK_MODBUS_CONTRACT := ../../contracts/modbus/mock-modbus.devices.json
seed-db:
	$(COMPOSE) exec -T $(APP) mkdir -p /app/tests/seed_db
	$(COMPOSE) cp tests/seed_db/. $(APP):/app/tests/seed_db/
	$(COMPOSE) cp $(MOCK_MODBUS_CONTRACT) $(APP):/app/tests/seed_db/
	$(COMPOSE) exec -T $(APP) python tests/seed_db/seed_db.py

# ---------------------------------------------------------------------------
# Cloud cost control (GKE) — stop everything billable when not in use, and bring
# it all back "ready". Scale-to-zero approach: keeps the cluster/ArgoCD config and
# Cloud SQL DATA, just idles compute. Override the vars if your names differ.
# ---------------------------------------------------------------------------
GCP_PROJECT  ?= prd-pae-backend-ot
GCP_REGION   ?= us-central1
SQL_INSTANCE ?= pae-backend-ot-pg-prod
K8S_NS       ?= pae-backend-ot-prod

ifeq ($(OS),Windows_NT)
# kubectl needs gke-gcloud-auth-plugin, which is on the PowerShell PATH but usually not on
# make's recipe PATH — delegate to the PowerShell script (same logic).
cloud-down:
	@powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cloud.ps1 cloud-down
cloud-up:
	@powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cloud.ps1 cloud-up
else
# Stop all billable compute (app + redis + ArgoCD scaled to 0, Cloud SQL stopped).
# Idle cost ≈ Cloud SQL storage only (~$2-3/mo). Data is preserved.
cloud-down:
	@echo ">> Stopping ArgoCD (so it won't scale things back up)..."
	@kubectl -n argocd scale statefulset --all --replicas=0
	@kubectl -n argocd scale deploy --all --replicas=0
	@echo ">> Removing HPA (it would otherwise force min replicas)..."
	@kubectl -n $(K8S_NS) delete hpa pae-backend-ot --ignore-not-found
	@echo ">> Scaling app + redis to 0..."
	@kubectl -n $(K8S_NS) scale deploy pae-backend-ot redis --replicas=0
	@echo ">> Stopping Cloud SQL..."
	@gcloud sql instances patch $(SQL_INSTANCE) --project=$(GCP_PROJECT) --activation-policy=NEVER --quiet
	@echo ">> cloud-down complete. Billing minimized (data preserved)."

# Start Cloud SQL, bring ArgoCD back, scale workloads up, let ArgoCD reconcile.
cloud-up:
	@echo ">> Starting Cloud SQL..."
	@gcloud sql instances patch $(SQL_INSTANCE) --project=$(GCP_PROJECT) --activation-policy=ALWAYS --quiet
	@echo ">> Waiting for Cloud SQL to be RUNNABLE..."
	@until [ "$$(gcloud sql instances describe $(SQL_INSTANCE) --project=$(GCP_PROJECT) --format='value(state)')" = "RUNNABLE" ]; do sleep 10; echo "   ...still starting"; done
	@echo ">> Bringing ArgoCD back..."
	@kubectl -n argocd scale statefulset --all --replicas=1
	@kubectl -n argocd scale deploy --all --replicas=1
	@kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=180s
	@kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s
	@echo ">> Scaling redis + app back up..."
	@kubectl -n $(K8S_NS) scale deploy redis --replicas=1
	@kubectl -n $(K8S_NS) rollout status deploy/redis --timeout=120s
	@kubectl -n $(K8S_NS) scale deploy pae-backend-ot --replicas=2
	@kubectl -n $(K8S_NS) rollout status deploy/pae-backend-ot --timeout=240s
	@echo ">> Nudging ArgoCD to reconcile (recreates HPA, marks Synced)..."
	@kubectl -n argocd annotate application pae-backend-ot-prod argocd.argoproj.io/refresh=hard --overwrite >/dev/null
	@echo ">> cloud-up complete. App is ready."
endif
