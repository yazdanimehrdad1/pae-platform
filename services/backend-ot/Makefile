.PHONY: help network up down build rebuild up-build up-rebuild restart logs shell clean ps health dev test-setup test test-unit test-integration lint lint-fix format migrate apply-migration run seed-db cloud-down cloud-up

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
# On Windows, kubectl needs gke-gcloud-auth-plugin, which is on the PowerShell PATH
# but usually NOT on GNU make's recipe-shell PATH — so `make cloud-down` fails with
# "gke-gcloud-auth-plugin.exe not found". Delegate to make.ps1, which runs in a fresh
# PowerShell that has the plugin. (Same logic, one source of truth in make.ps1.)
cloud-down:
	@powershell -NoProfile -ExecutionPolicy Bypass -File make.ps1 cloud-down
cloud-up:
	@powershell -NoProfile -ExecutionPolicy Bypass -File make.ps1 cloud-up
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

# Default target
help:
	@echo "Available commands:"
	@echo "  make up       - Start the containers"
	@echo "  make up-build - Build and start containers"
	@echo "  make down     - Stop and remove containers"
	@echo "  make build     - Build the Docker image (uses cache)"
	@echo "  make rebuild   - Rebuild the Docker image (no cache, forces fresh build)"
	@echo "  make up-rebuild - Rebuild (no cache) and start containers"
	@echo "  make restart   - Restart the containers"
	@echo "  make logs     - View container logs"
	@echo "  make shell    - Open a shell in the container"
	@echo "  make ps       - View container status"
	@echo "  make health   - Check service health"
	@echo "  make clean    - Stop containers and remove images"
	@echo ""
	@echo "Development commands:"
	@echo "  make dev        - Start development environment"
	@echo "  make test-setup - Prepare test environment (ensure containers are running)"
	@echo "  make test       - Run unit + integration tests (all via Docker)"
	@echo "  make test-unit  - Run unit tests via Docker (TEST_PATH=... to narrow)"
	@echo "  make test-integration - Run integration tests on a throwaway postgres+redis stack"
	@echo "  make lint       - Run linters (ruff, mypy)"
	@echo "  make format     - Format code (black, ruff)"
	@echo "  make migrate    - Run database migrations"
	@echo "  make apply-migration - Apply database migrations (in container)"
	@echo "  make run        - Run service locally (non-Docker)"
	@echo "  make seed-db    - Seed the database in container"

# Ensure the shared Docker network exists (idempotent)
network:
	-@docker network create pae-shared-network 2>&1
	@echo "pae-shared-network ready"

# Start containers (ensures postgres is healthy, then starts services)
up: network
	@echo "Starting services..."
	@docker-compose -f docker-compose.yaml up -d --wait postgres redis
	@echo "PostgreSQL and Redis are ready!"
	@echo "Starting application service (migrations will run automatically)..."
	@docker-compose -f docker-compose.yaml up -d pae-backend-ot

# Stop and remove containers
down:
	docker-compose -f docker-compose.yaml down

# Build the Docker image (uses cache)
build:
	docker-compose -f docker-compose.yaml build

# Rebuild the Docker image (no cache - forces fresh build)
rebuild:
	docker-compose -f docker-compose.yaml build --no-cache
	docker-compose -f docker-compose.yaml up -d --wait postgres redis
	docker-compose -f docker-compose.yaml up -d pae-backend-ot

# Build and start containers
up-build: network
	@echo "Building and starting services..."
	@docker-compose -f docker-compose.yaml build
	@docker-compose -f docker-compose.yaml up -d --wait postgres redis
	@echo "PostgreSQL and Redis are ready!"
	@echo "Starting application service (migrations will run automatically)..."
	@docker-compose -f docker-compose.yaml up -d pae-backend-ot

# Rebuild and start containers (no cache)
up-rebuild: network
	@echo "Rebuilding and starting services..."
	@docker-compose -f docker-compose.yaml build --no-cache
	@docker-compose -f docker-compose.yaml up -d --wait postgres redis
	@echo "PostgreSQL and Redis are ready!"
	@echo "Starting application service (migrations will run automatically)..."
	@docker-compose -f docker-compose.yaml up -d pae-backend-ot

# Restart containers
restart:
	docker-compose -f docker-compose.yaml restart

# View logs
logs:
	docker-compose -f docker-compose.yaml logs -f pae-backend-ot

# Open a shell in the container
shell:
	docker-compose -f docker-compose.yaml exec pae-backend-ot /bin/bash

# Clean up containers and images
clean:
	docker-compose -f docker-compose.yaml down
	docker rmi pae-backend-ot 2>/dev/null || true

# View container status
ps:
	docker-compose -f docker-compose.yaml ps

# Check service health
health:
	@curl -s http://localhost:8000/api/healthz || echo "Service not responding"

# Development commands
dev:
	@echo "Starting development environment..."
	# TODO: Add development setup (install deps, run tests, etc.)

# Prepare test environment - ensure Redis container is running
test-setup:
	@echo "Preparing test environment..."
	@docker-compose -f docker-compose.yaml up -d --wait redis
	@echo "Redis is ready!"

# Runs pytest in a throwaway container matching the app's Python (no local Python
# needed). The named volume caches pip downloads between runs.
# Override the target with TEST_PATH, e.g. `make test-unit TEST_PATH=tests/unit/helpers`.
PYTEST_DOCKER = docker run --rm -v "$(CURDIR):/app" -v pae-backend-ot-pip-cache:/root/.cache/pip \
	-w /app -e PYTHONPATH=src python:3.11-slim \
	bash -c "pip install -q --root-user-action=ignore -e '.[dev]' && pytest $(1) -v --color=yes -rfE"

# Integration tests run on a throwaway postgres + redis (docker-compose.test.yaml: tmpfs,
# no host ports, own project name), torn down after every run — never the dev stack.
TEST_COMPOSE = docker compose -p pae-backend-ot-test -f docker-compose.test.yaml

# Run all tests: unit first (fast, fails early), then integration
test: test-unit test-integration

# Run unit tests only - no I/O, so no containers needed
test-unit:
	@echo "Running unit tests..."
	$(call PYTEST_DOCKER,$(or $(TEST_PATH),tests/unit))

# Run integration tests on the throwaway stack; always tears it down, keeps pytest's exit code
ifeq ($(OS),Windows_NT)
# GNU make on Windows runs recipes in cmd.exe, which can't do the POSIX env/redirect/exit
# handling below. Delegate to make.ps1 (same logic), like cloud-down/cloud-up do.
test-integration:
	@powershell -NoProfile -ExecutionPolicy Bypass -File make.ps1 test-integration $(TEST_PATH)
else
test-integration:
	@echo "Running integration tests (throwaway stack)..."
	@docker volume create pae-backend-ot-pip-cache >/dev/null
	@PYTEST_TARGET=$(or $(TEST_PATH),tests/integration) $(TEST_COMPOSE) run --rm tests; \
		status=$$?; $(TEST_COMPOSE) down --remove-orphans >/dev/null 2>&1; exit $$status
endif

# Run linting (ruff is the CI-blocking gate). Runs in Docker so no local Python
# is required; $(CURDIR) resolves to a Docker-compatible path on Linux and Windows.
lint:
	docker run --rm -v "$(CURDIR):/io" ghcr.io/astral-sh/ruff:0.16.0 check src/ tests/

# Auto-fix lint issues (ruff only; B904 exception chaining must be fixed by hand).
lint-fix:
	docker run --rm -v "$(CURDIR):/io" ghcr.io/astral-sh/ruff:0.16.0 check --fix src/ tests/

# Format code
format:
	@echo "Formatting Python files with black..."
	@docker-compose -f docker-compose.yaml exec pae-backend-ot black src/ 2>/dev/null || echo "Note: Running black in container..."
	@echo "Running ruff to fix import sorting and other issues..."
	@docker-compose -f docker-compose.yaml exec pae-backend-ot ruff check --fix src/ 2>/dev/null || echo "Note: Running ruff in container..."
	@echo "Formatting complete!"


# Run database migrations
migrate:
	@python scripts/migrate_db.py

# Apply database migrations (in container)
apply-migration:
	@docker-compose -f docker-compose.yaml exec pae-backend-ot python scripts/migrate_db.py

# Run the service locally (non-Docker)
run:
	@cd src && python -m main

# Seed database with development mock data (copies files into running container first)
seed-db:
	@echo "Copying seed files into container..."
	@docker cp tests/seed_db/. pae-backend-ot:/app/tests/seed_db/
	@echo "Running seed script..."
	@docker-compose -f docker-compose.yaml exec pae-backend-ot python tests/seed_db/seed_db.py