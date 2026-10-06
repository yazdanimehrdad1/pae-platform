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
SERVICES := backend-ot mock-modbus web-plusdas powerflow
# `svc=<name>` narrows fan-out targets and dev-stack targets to one service.
TARGET_SERVICES := $(or $(svc),$(SERVICES))

# DEV stack. The root .env (optional, see .env.example) holds host-port overrides only
# (plain KEY=VALUE lines), so make can read it too: targets like `e2e` then see the same ports.
-include .env
DEV_COMPOSE := docker compose -f $(CURDIR)/deploy/compose/dev.yaml $(if $(wildcard .env),--env-file $(CURDIR)/.env)

FANOUT_TARGETS := install lint format typecheck test test-integration build contract
.PHONY: help up down down-all stop-all restart logs ps seed seed-mock-modbus seed-2bess-1pv seed-powerflow-site e2e e2e-2bess-1pv check check-boundaries contracts-check hooks $(FANOUT_TARGETS)

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
	@echo "                     (postgres/redis data, incl. powerflow's sites/maps/profile edits),"
	@echo "                     images (built and pulled) and networks"
	@echo "  restart / ps / logs [svc=...]"
	@echo "  seed-mock-modbus   seed backend-ot with the mock-modbus site (Alpha Solar Farm), built"
	@echo "                     from mock-modbus's contract"
	@echo "  seed-2bess-1pv     seed backend-ot with powerflow's 2bess_1pv site as a real site (site,"
	@echo "                     devices, register maps, SLD from powerflow's contracts), then make it"
	@echo "                     powerflow's active site and start it"
	@echo "  seed-powerflow-site SITE=<site>  the same for any powerflow default site"
	@echo "  e2e                check backend-ot is polling mock-modbus and agrees with the contract"
	@echo "  e2e-2bess-1pv      check backend-ot's readings of 2bess_1pv agree with powerflow"
	@echo ""
	@echo "Per service (runs in every service, or svc=<name>): $(FANOUT_TARGETS)"
	@echo "  check              lint + typecheck + test for every service, then check-boundaries + contracts-check"
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
# network. The next `make up` re-pulls/rebuilds images and starts with empty databases (seed-*
# again). Not touched: other Docker projects, the *-test-* stacks and the external
# backend-ot-uv-cache / powerflow-uv-cache volumes.
down-all:
	@echo "==> dev stack (pae-dev): down, deleting volumes, images, network"
	@$(DEV_COMPOSE) down --volumes --rmi all --remove-orphans
	@for service in $(SERVICES); do \
		echo "==> $$service (standalone): down-all"; \
		$(MAKE) -s --no-print-directory -C "services/$$service" down-all; \
	done

# Every platform container: the dev stack, then each service's standalone stack via that
# service's own `down` (the root never touches a service's compose file directly). Other
# Docker projects, including the integration-test stacks (backend-ot-test-*, powerflow-test-*),
# are left alone.
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

# backend-ot's own seed targets, pointed at the dev stack instead of its standalone stack.
seed:
	@echo "make seed was renamed: make seed-mock-modbus (the mock-modbus site) or"
	@echo "make seed-2bess-1pv (powerflow's 2bess_1pv site)"; exit 2

seed-mock-modbus:
	$(MAKE) -C services/backend-ot seed-db-mock-modbus COMPOSE="$(DEV_COMPOSE)"

# Seed one of powerflow's default sites into backend-ot, then make it powerflow's active site
# and run it, so backend-ot polls the layout it was seeded with. Each site gets its own target.
POWERFLOW_API := http://localhost:$(or $(POWERFLOW_HTTP_PORT),8020)/api
seed-powerflow-site:
	@test -n "$(SITE)" || { echo "usage: make seed-powerflow-site SITE=<powerflow site>"; exit 2; }
	@curl -fsS -o /dev/null $(POWERFLOW_API)/health || { \
		echo "powerflow isn't reachable at $(POWERFLOW_API): run make up first"; exit 1; }
	$(MAKE) -C services/backend-ot seed-db-powerflow SITE=$(SITE) COMPOSE="$(DEV_COMPOSE)"
	curl -fsS -o /dev/null -X POST $(POWERFLOW_API)/sim/stop
	curl -fsS -o /dev/null -X POST $(POWERFLOW_API)/sites/$(SITE)/activate
	curl -fsS -o /dev/null -X POST $(POWERFLOW_API)/sim/start
	@echo "powerflow is running $(SITE); backend-ot polls it at powerflow:502"

seed-2bess-1pv:
	$(MAKE) seed-powerflow-site SITE=2bess_1pv

# E2E against the running dev stack: backend-ot polls mock-modbus and agrees with the contract.
E2E_API := http://localhost:$(or $(BACKEND_OT_HTTP_PORT),8000)/api
e2e:
	uv run --no-project python scripts/e2e/check_backend_reads_mock.py --api $(E2E_API)

# E2E: backend-ot's readings of a seeded powerflow site agree with powerflow's HTTP device view.
e2e-2bess-1pv:
	uv run --no-project python scripts/e2e/check_backend_reads_powerflow.py --api $(E2E_API) \
		--powerflow-api $(POWERFLOW_API) --site 2bess_1pv

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
check: lint typecheck test check-boundaries contracts-check

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
