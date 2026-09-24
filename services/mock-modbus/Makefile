# mock-modbus — service Makefile. DEV-ONLY service: never part of a production manifest.
#
# Run from anywhere with `make -C services/mock-modbus <target>` (or from this directory).
# Standard targets (same names in every service): install lint format typecheck test
# build up down logs run. Tooling: uv only; every Python tool runs from uv.lock.

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
# Stop Git-Bash rewriting container paths like /opt into C:/Program Files/Git/opt.
export MSYS_NO_PATHCONV := 1
export MSYS2_ARG_CONV_EXCL := *
endif
.SHELLFLAGS := -ec

.DEFAULT_GOAL := help
.PHONY: help install lint lint-fix format typecheck test contract build rebuild up down restart \
	logs ps clean network run

COMPOSE := docker compose -f docker-compose.yaml
# Published register map (contracts/ is the only directory shared between services).
CONTRACT_FILE := ../../contracts/modbus/mock-modbus.devices.json
UV_RUN  := uv run --frozen

# Port for `make run` on the host (502 is privileged on Linux/macOS).
RUN_PORT ?= 5020

help:
	@echo "mock-modbus (DEV-ONLY) — make -C services/mock-modbus <target>"
	@echo ""
	@echo "Develop (host, via uv):"
	@echo "  install          uv sync (creates .venv from uv.lock, incl. dev group)"
	@echo "  lint / lint-fix  ruff check app tests / auto-fix"
	@echo "  format           ruff --fix (import order, pyupgrade)"
	@echo "  typecheck        (no type checker configured yet)"
	@echo "  test             pytest: starts the server itself on a free port; no Docker"
	@echo "  run              run the server on the host (RUN_PORT=$(RUN_PORT))"
	@echo "  contract         regenerate $(CONTRACT_FILE) from the device files"
	@echo ""
	@echo "Containers (docker compose):"
	@echo "  build / rebuild  build the image (rebuild = no cache)"
	@echo "  up / down / restart / logs / ps / clean"

# ---------------------------------------------------------------------------
# Develop
# ---------------------------------------------------------------------------
install:
	uv sync --frozen

lint:
	$(UV_RUN) ruff check app tests

lint-fix:
	$(UV_RUN) ruff check --fix app tests

format:
	$(UV_RUN) ruff check --fix app tests

typecheck:
	@echo "typecheck: no type checker configured for mock-modbus yet (see MONOREPO_ROADMAP.md R5)"

test:
	$(UV_RUN) pytest $(or $(TEST_PATH),tests) -v --color=yes -rfE

# Run after any device/register change; `make test` fails while the contract is stale.
contract:
	$(UV_RUN) python scripts/export_contract.py --output $(CONTRACT_FILE)

run:
	MODBUS_PORT=$(RUN_PORT) $(UV_RUN) python -m app.server

# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------
# Shared external network the compose file still expects (removed in roadmap Phase 3).
network:
	@docker network inspect pae-shared-network >/dev/null 2>&1 || docker network create pae-shared-network >/dev/null
	@echo "pae-shared-network ready"

build: network
	$(COMPOSE) build

rebuild: network
	$(COMPOSE) build --no-cache

up: network
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

restart: down up

logs:
	$(COMPOSE) logs -f mock-modbus

ps:
	$(COMPOSE) ps

# Removes this project's containers and the images it built.
clean:
	$(COMPOSE) down --rmi local
