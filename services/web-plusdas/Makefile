# web-plusdas — service Makefile (the PAE frontend: Vite + React SPA, served by nginx).
#
# Run from anywhere with `make -C services/web-plusdas <target>` (or from this directory).
# Standard targets (same names in every service): install lint format typecheck test
# test-integration build up down logs run. Tooling: npm only; every tool runs from
# package-lock.json (host targets run `npm ci` first when node_modules is missing or stale).

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
# Stop Git-Bash rewriting container paths like /usr/share/nginx into C:/Program Files/Git/usr/....
export MSYS_NO_PATHCONV := 1
export MSYS2_ARG_CONV_EXCL := *
endif
.SHELLFLAGS := -ec

.DEFAULT_GOAL := help
.PHONY: require-no-dev-stack help install lint lint-fix format typecheck test test-integration build rebuild \
	up down down-all restart logs ps clean run

# Standalone container. Host port: WEB_PLUSDAS_HTTP_PORT (default 5173). nginx forwards /api to
# WEB_PLUSDAS_API_UPSTREAM (default: backend-ot's host port via host.docker.internal).
COMPOSE   := docker compose -f compose.yaml
HTTP_PORT := $(or $(WEB_PLUSDAS_HTTP_PORT),5173)

# Port for `make run` (the Vite dev server), so it can run beside the container on 5173.
RUN_PORT ?= 5174

# npm writes this file on every install; it is older than the lockfile when node_modules is stale.
NODE_MODULES := node_modules/.package-lock.json

help:
	@echo "web-plusdas — make -C services/web-plusdas <target>"
	@echo ""
	@echo "Develop (host, via npm):"
	@echo "  install          npm ci (node_modules from package-lock.json)"
	@echo "  lint / lint-fix  eslint . / auto-fix"
	@echo "  format           eslint --fix (no formatter configured)"
	@echo "  typecheck        tsc --noEmit on the app (blocking)"
	@echo "  test             (no unit tests yet)"
	@echo "  test-integration check the running container: SPA, caching, /api same-origin proxy"
	@echo "  run              Vite dev server on http://localhost:$(RUN_PORT) (/api -> localhost:8000)"
	@echo ""
	@echo "Containers (docker compose):"
	@echo "  build / rebuild  build the image (rebuild = no cache)"
	@echo "  up / down / restart / logs / ps / clean"
	@echo "  down-all         DESTRUCTIVE: down + delete volumes, images, network"

# ---------------------------------------------------------------------------
# Develop
# ---------------------------------------------------------------------------
$(NODE_MODULES): package.json package-lock.json
	npm ci --no-audit --no-fund

install:
	npm ci --no-audit --no-fund

lint: $(NODE_MODULES)
	npm run lint

lint-fix: $(NODE_MODULES)
	npm run lint -- --fix

format: $(NODE_MODULES)
	npm run lint -- --fix

typecheck: $(NODE_MODULES)
	npm run typecheck

test:
	@echo "test: no unit tests configured for web-plusdas yet (see docs/api-types-follow-up.md)"

# Needs the container running: the root dev stack (`make up` at the repo root) or `make up` here.
test-integration:
	node scripts/check_same_origin.mjs --url http://localhost:$(HTTP_PORT)

run: $(NODE_MODULES)
	npm run dev -- --port $(RUN_PORT)

# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------
# The monorepo root takes priority: while its dev stack (compose project pae-dev) is running,
# this service already runs there. Run `make down` at the repo root before running it alone.
require-no-dev-stack:
	@if docker compose ls -q 2>/dev/null | grep -qx pae-dev; then \
		echo "web-plusdas: the platform dev stack (pae-dev) is running; run 'make down' at the repo root first" >&2; \
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

# DESTRUCTIVE: also deletes this stack's volumes (it has none), the images it uses (built and
# pulled) and its network. `down` keeps them.
down-all:
	$(COMPOSE) down --volumes --rmi all --remove-orphans

restart: down up

logs:
	$(COMPOSE) logs -f web-plusdas

ps:
	$(COMPOSE) ps

# Removes this project's containers and the images it built.
clean:
	$(COMPOSE) down --rmi local
