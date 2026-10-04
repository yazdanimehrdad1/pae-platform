# powerflow — service Makefile.
#
# Run from anywhere with `make -C services/powerflow <target>` (or from this directory).
# Standard targets (same names in every service): install lint format typecheck test
# build up down logs run contract. Tooling: uv only; every Python tool runs from uv.lock.

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
.PHONY: require-no-dev-stack help install lint lint-fix format typecheck test test-integration contract \
	profiles modbus-maps postman build rebuild up down down-all restart logs ps clean run

# Standalone stack (powerflow + its Postgres). Host ports: POWERFLOW_HTTP_PORT (8020),
# POWERFLOW_POSTGRES_PORT (5436), POWERFLOW_MODBUS_PORT (1502).
COMPOSE := docker compose -f compose.yaml

# Integration-test stack: one isolated compose project per worktree, so parallel worktrees never
# share (or tear down) each other's throwaway Postgres.
WORKTREE_ID  := $(shell basename "$(abspath $(CURDIR)/../..)" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9\n' '-')
TEST_COMPOSE := docker compose -p powerflow-test-$(WORKTREE_ID) -f compose.test.yaml
APP     := powerflow
UV_RUN  := uv run --frozen
# Published contracts (contracts/ is the only directory shared between services): the HTTP API
# and the protocol-neutral point lists. `make test` fails while they are stale.
CONTRACT_FILE := ../../contracts/openapi/powerflow.openapi.json
POINTS_CONTRACT_FILE := ../../contracts/powerflow/points.json
REGISTERS_CONTRACT_FILE := ../../contracts/modbus/powerflow.registers.json

help:
	@echo "powerflow — make -C services/powerflow <target>"
	@echo ""
	@echo "Develop (host, via uv):"
	@echo "  install          uv sync (creates .venv from uv.lock, incl. dev group)"
	@echo "  lint / lint-fix  ruff check src tests / auto-fix"
	@echo "  format           ruff format + ruff --fix"
	@echo "  typecheck        pyright (blocking)"
	@echo "  test             unit tests (pytest, no Docker, in-memory config store)"
	@echo "  test-integration integration tests on a throwaway Postgres (Docker)"
	@echo "  run              run the API on the host (port 8020; needs Postgres on 5436)"
	@echo "  contract         regenerate the OpenAPI, points and Modbus registers contracts"
	@echo "  profiles         regenerate the profile scenarios in site_config/profiles/"
	@echo "  modbus-maps      regenerate the default Modbus map files (the DB is untouched)"
	@echo "  postman          regenerate postman/powerflow.postman_collection.json"
	@echo ""
	@echo "Containers (docker compose):"
	@echo "  build / rebuild  build the image (rebuild = no cache)"
	@echo "  up / down / restart / logs / ps / clean"
	@echo "  down-all         DESTRUCTIVE: down + delete volumes, images, network"

# ---------------------------------------------------------------------------
# Develop
# ---------------------------------------------------------------------------
install:
	uv sync --frozen

lint:
	$(UV_RUN) ruff check src tests scripts

lint-fix:
	$(UV_RUN) ruff check --fix src tests scripts

format:
	$(UV_RUN) ruff format src tests scripts
	$(UV_RUN) ruff check --fix src tests scripts

typecheck:
	$(UV_RUN) pyright

test:
	$(UV_RUN) pytest $(or $(TEST_PATH),tests --ignore=tests/integration) -v --color=yes -rfE

test-integration:
	@echo "Running integration tests (project powerflow-test-$(WORKTREE_ID))..."
	@docker volume create powerflow-uv-cache >/dev/null
	@status=0; PYTEST_TARGET=$(or $(TEST_PATH),tests/integration) $(TEST_COMPOSE) run --rm tests || status=$$?; 		$(TEST_COMPOSE) down --remove-orphans >/dev/null 2>&1 || true; exit $$status

# Run after any route/model change; `make test` fails while the contract is stale.
contract:
	$(UV_RUN) python scripts/export_openapi.py --output $(CONTRACT_FILE) \
		--points-output $(POINTS_CONTRACT_FILE) --registers-output $(REGISTERS_CONTRACT_FILE)

profiles:
	$(UV_RUN) python scripts/make_profiles.py

modbus-maps:
	$(UV_RUN) python scripts/make_modbus_maps.py

# Run after any route change; `make test` fails while the collection is stale.
postman:
	$(UV_RUN) python scripts/export_postman.py

run:
	$(UV_RUN) uvicorn powerflow.app:app --app-dir src --host 127.0.0.1 --port 8020 --reload

# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------
# The monorepo root takes priority: while its dev stack (compose project pae-dev) is running,
# this service already runs there. Run `make down` at the repo root before running it alone.
require-no-dev-stack:
	@if docker compose ls -q 2>/dev/null | grep -qx pae-dev; then \
		echo "powerflow: the platform dev stack (pae-dev) is running; run 'make down' at the repo root first" >&2; \
		exit 1; \
	fi

build: require-no-dev-stack
	$(COMPOSE) build

rebuild: require-no-dev-stack
	$(COMPOSE) build --no-cache

up: require-no-dev-stack
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

# DESTRUCTIVE: also deletes this stack's data volumes, the images it uses (built and pulled)
# and its network. `down` keeps the volumes.
down-all:
	$(COMPOSE) down --volumes --rmi all --remove-orphans

restart: down up

logs:
	$(COMPOSE) logs -f $(APP)

ps:
	$(COMPOSE) ps

# Removes this project's containers and the images it built (volumes are kept).
clean:
	$(COMPOSE) down --rmi local
