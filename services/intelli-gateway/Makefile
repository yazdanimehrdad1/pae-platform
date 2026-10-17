# intelli-gateway — service Makefile.
#
# Run from anywhere with `make -C services/intelli-gateway <target>` (or from this directory).
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
.PHONY: require-no-dev-stack help install lint lint-fix format typecheck test test-integration contract build rebuild up down down-all restart \
	logs ps clean run

# Standalone stack. Host port: INTELLI_GATEWAY_HTTP_PORT (default 8030).
COMPOSE := docker compose -f compose.yaml
APP     := intelli-gateway
UV_RUN  := uv run --frozen
# Published HTTP API (contracts/ is the only directory shared between services).
CONTRACT_FILE := ../../contracts/openapi/intelli-gateway.openapi.json

help:
	@echo "intelli-gateway — make -C services/intelli-gateway <target>"
	@echo ""
	@echo "Develop (host, via uv):"
	@echo "  install          uv sync (creates .venv from uv.lock, incl. dev group)"
	@echo "  lint / lint-fix  ruff check src tests / auto-fix"
	@echo "  format           ruff format + ruff --fix"
	@echo "  typecheck        pyright (blocking; strict except api/, fake_data/, knowledge/, prompts/)"
	@echo "  test             unit tests (pytest, no Docker, fake data, mocked Claude)"
	@echo "  test-integration real Claude API test (needs ANTHROPIC_API_KEY; costs tokens)"
	@echo "  run              run the API on the host (port 8030)"
	@echo "  contract         regenerate $(CONTRACT_FILE) (the OpenAPI spec)"
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

# Run after any route/model change; `make test` fails while the contract is stale.
# Calls the real Claude API (tokens cost money); skipped unless RUN_LLM_TESTS=1.
test-integration:
	RUN_LLM_TESTS=1 $(UV_RUN) pytest tests/integration -v --color=yes -rfE

contract:
	$(UV_RUN) python scripts/export_openapi.py --output $(CONTRACT_FILE)

run:
	$(UV_RUN) uvicorn intelli_gateway.app:app --app-dir src --host 127.0.0.1 --port 8030 --reload

# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------
# The monorepo root takes priority: while its dev stack (compose project pae-dev) is running,
# this service already runs there. Run `make down` at the repo root before running it alone.
require-no-dev-stack:
	@if docker compose ls -q 2>/dev/null | grep -qx pae-dev; then \
		echo "intelli-gateway: the platform dev stack (pae-dev) is running; run 'make down' at the repo root first" >&2; \
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
