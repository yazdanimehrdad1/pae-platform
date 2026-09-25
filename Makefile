# pae-platform — monorepo root Makefile.
#
# Two jobs, nothing else:
#   1. the DEV stack: every service together (deploy/compose/dev.yaml);
#   2. fan standard targets out to services: `make test` runs `make -C services/<svc> test`
#      for every service; `make test svc=backend-ot` narrows it to one.
# Service logic lives in each service's own Makefile — never here.

# ---------------------------------------------------------------------------
# Shell: POSIX sh everywhere (Git for Windows' sh on Windows; 8.3 path, no spaces).
# ---------------------------------------------------------------------------
ifeq ($(OS),Windows_NT)
GIT_SH ?= $(firstword $(wildcard C:/PROGRA~1/Git/bin/sh.exe C:/PROGRA~1/Git/usr/bin/sh.exe $(LOCALAPPDATA)/Programs/Git/bin/sh.exe))
ifeq ($(GIT_SH),)
$(error Git for Windows sh.exe not found; pass GIT_SH=<path to sh.exe>)
endif
SHELL := $(GIT_SH)
export MSYS_NO_PATHCONV := 1
export MSYS2_ARG_CONV_EXCL := *
endif
.SHELLFLAGS := -ec

.DEFAULT_GOAL := help

# Every service under services/. A new service is added here (the new-service skill does it).
SERVICES := backend-ot mock-modbus
# `svc=<name>` narrows fan-out targets and dev-stack targets to one service.
TARGET_SERVICES := $(or $(svc),$(SERVICES))

# DEV stack. The root .env (optional, see .env.example) holds host-port overrides only
# (plain KEY=VALUE lines), so make can read it too: targets like `e2e` then see the same ports.
-include .env
DEV_COMPOSE := docker compose -f $(CURDIR)/deploy/compose/dev.yaml $(if $(wildcard .env),--env-file $(CURDIR)/.env)

FANOUT_TARGETS := install lint format typecheck test test-integration build contract
.PHONY: help up down down-all stop-all restart logs ps seed e2e check check-boundaries contracts-check hooks $(FANOUT_TARGETS)

help:
	@echo "pae-platform — monorepo root"
	@echo ""
	@echo "Dev stack (all services on one network; mock-modbus included, DEV-ONLY):"
	@echo "  up [svc=...]       RESET: stop every platform container (dev stack + any service started"
	@echo "                     on its own), then build + start everything (or one service and its"
	@echo "                     deps) and wait for healthy"
	@echo "  down               stop every platform container, both modes (volumes kept)."
	@echo "                     Run it before starting a single service with make -C services/<svc> up"
	@echo "  down-all           DESTRUCTIVE: stop every platform container AND delete their volumes"
	@echo "                     (postgres/redis data), images (built and pulled) and networks"
	@echo "  restart / ps / logs [svc=...]"
	@echo "  seed               load backend-ot's dev data (built from mock-modbus's contract)"
	@echo "  e2e                check backend-ot is polling mock-modbus and agrees with the contract"
	@echo ""
	@echo "Per service (runs in every service, or svc=<name>): $(FANOUT_TARGETS)"
	@echo "  check              lint + test for every service, then check-boundaries + contracts-check"
	@echo "                     (stage regenerated contracts first)"
	@echo "  check-boundaries   no cross-service imports/paths; mock-modbus in no production manifest"
	@echo "  contracts-check    regenerate every contract; fail if contracts/ differs from the index"
	@echo "  hooks              enable the repo's git hooks (.githooks/pre-commit)"
	@echo ""
	@echo "Services: $(SERVICES)"
	@echo "Standalone: make -C services/<svc> <target>   (see each service's CLAUDE.md)"

# ---------------------------------------------------------------------------
# Dev stack
# ---------------------------------------------------------------------------
# Compose service names match service directory names by convention, so svc=<name>
# works for both the fan-out targets and the dev stack.
# The root takes priority: `up` always starts from a clean slate, so whatever was running
# (the dev stack, or services started on their own) is stopped first. Running a single service
# on its own is the exception: `make down` here first (the service Makefiles refuse to start
# while the dev stack is up). Volumes are always kept.
up: stop-all
	$(DEV_COMPOSE) up -d --build --wait $(svc)

down: stop-all

# DESTRUCTIVE clean slate: every platform stack (dev stack + each service's standalone stack,
# through that service's own `down-all`) loses its containers, data volumes, images and
# network. The next `make up` re-pulls/rebuilds images and starts with empty databases (seed
# again). Not touched: other Docker projects, the backend-ot-test-* stacks and the external
# backend-ot-uv-cache volume.
down-all:
	@echo "==> dev stack (pae-dev): down, deleting volumes, images, network"
	@$(DEV_COMPOSE) down --volumes --rmi all --remove-orphans
	@for service in $(SERVICES); do \
		echo "==> $$service (standalone): down-all"; \
		$(MAKE) -s --no-print-directory -C "services/$$service" down-all; \
	done

# Every platform container: the dev stack, then each service's standalone stack via that
# service's own `down` (the root never touches a service's compose file directly). Other
# Docker projects, including the integration-test stacks (backend-ot-test-*), are left alone.
stop-all:
	@echo "==> dev stack (pae-dev): down"
	@$(DEV_COMPOSE) down --remove-orphans
	@for service in $(SERVICES); do \
		echo "==> $$service (standalone): down"; \
		$(MAKE) -s --no-print-directory -C "services/$$service" down; \
	done

restart:
	$(DEV_COMPOSE) restart $(svc)

ps:
	$(DEV_COMPOSE) ps

logs:
	$(DEV_COMPOSE) logs -f $(svc)

# backend-ot's own seed target, pointed at the dev stack instead of its standalone stack.
seed:
	$(MAKE) -C services/backend-ot seed-db COMPOSE="$(DEV_COMPOSE)"

# E2E against the running dev stack: backend-ot polls mock-modbus and agrees with the contract.
E2E_API := http://localhost:$(or $(BACKEND_OT_HTTP_PORT),8000)/api
e2e:
	uv run --no-project python scripts/e2e/check_backend_reads_mock.py --api $(E2E_API)

# ---------------------------------------------------------------------------
# Fan-out: run the same target in each service that defines it (others are skipped).
# ---------------------------------------------------------------------------
$(FANOUT_TARGETS):
	@for service in $(TARGET_SERVICES); do \
		if [ ! -d "services/$$service" ]; then echo "unknown service: $$service" >&2; exit 2; fi; \
		if $(MAKE) -s -C "services/$$service" -n $@ >/dev/null 2>&1; then \
			echo "==> $$service: make $@"; \
			$(MAKE) --no-print-directory -C "services/$$service" $@; \
		else \
			echo "==> $$service: no '$@' target, skipped"; \
		fi; \
	done

# contracts-check compares with the git index: stage regenerated contracts before `make check`.
check: lint test check-boundaries contracts-check

# Stdlib-only script; `uv run --no-project` just supplies a Python.
check-boundaries:
	uv run --no-project python scripts/check_boundaries.py

hooks:
	git config core.hooksPath .githooks
	@echo "hooks: enabled .githooks/ (pre-commit: lint changed services, check-boundaries, contracts-check)"

# Regenerates every published contract (the `contract` fan-out), then fails if contracts/ now
# differs from what is staged/committed, or has untracked files. Compares against the index,
# so a regenerated-and-staged contract passes (the pre-commit case).
# Hand-written docs (contracts/**/*.md) are not generated, so they are not compared.
CONTRACT_FILES := contracts/ ":(exclude,glob)contracts/**/*.md"
contracts-check: contract
	@git diff --exit-code --stat -- $(CONTRACT_FILES) || { echo "contracts-check: contracts/ is stale; stage the regenerated files" >&2; exit 1; }
	@untracked="$$(git ls-files --others --exclude-standard -- $(CONTRACT_FILES))"; \
		if [ -n "$$untracked" ]; then echo "contracts-check: untracked contract files:" >&2; echo "$$untracked" >&2; exit 1; fi
	@echo "contracts-check: contracts/ is current"
