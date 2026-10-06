# mobile-plusdas — service Makefile (the PAE mobile app: Expo / React Native, iOS + Android).
#
# Run from anywhere with `make -C services/mobile-plusdas <target>` (or from this directory).
# Standard targets: install lint format typecheck test build run. The app runs on phones, not in
# Docker: up/down/down-all/logs exist only so root loops (`make up`, `make down-all`) pass through.
# Tooling: npm only; every tool runs from package-lock.json.

# ---------------------------------------------------------------------------
# Shell: POSIX sh everywhere. On Windows, point GNU make at Git for Windows' sh (8.3 path).
# ---------------------------------------------------------------------------
ifeq ($(OS),Windows_NT)
GIT_SH ?= $(firstword $(wildcard C:/PROGRA~1/Git/bin/sh.exe C:/PROGRA~1/Git/usr/bin/sh.exe $(LOCALAPPDATA)/Programs/Git/bin/sh.exe))
ifeq ($(GIT_SH),)
$(error Git for Windows sh.exe not found; pass GIT_SH=<path to sh.exe>)
endif
SHELL := $(GIT_SH)
endif
.SHELLFLAGS := -ec

.DEFAULT_GOAL := help
.PHONY: help install lint lint-fix format typecheck test api-types build run eas-build-dev eas-build-preview \
	up down down-all logs clean

# Metro (the dev server Expo Go / dev builds load the app from).
RUN_PORT ?= 8081

# npm writes this file on every install; it is older than the lockfile when node_modules is stale.
NODE_MODULES := node_modules/.package-lock.json

help:
	@echo "mobile-plusdas — make -C services/mobile-plusdas <target>"
	@echo ""
	@echo "Develop (host, via npm):"
	@echo "  install          npm ci (node_modules from package-lock.json)"
	@echo "  lint / lint-fix  eslint . / auto-fix"
	@echo "  format           prettier --write ."
	@echo "  typecheck        tsc --noEmit (blocking)"
	@echo "  test             API types match the contract, then jest (unit + component, no device)"
	@echo "  api-types        regenerate src/api/generated/backend-ot.ts from the contract"
	@echo "  build            bundle check: expo export for Android and iOS into dist/"
	@echo "  run              Metro on port $(RUN_PORT); open in a dev build or Expo Go (same Wi-Fi)"
	@echo ""
	@echo "Phone builds (EAS, needs 'eas login' and EAS_PROJECT_ID):"
	@echo "  eas-build-dev      development build (push works; installs beside Expo Go)"
	@echo "  eas-build-preview  internal release build for TestFlight / Play internal testing"
	@echo ""
	@echo "Not containerized: up / down / down-all / logs are no-ops."

$(NODE_MODULES): package.json package-lock.json
	npm ci --no-audit --no-fund

install:
	npm ci --no-audit --no-fund

lint: $(NODE_MODULES)
	npm run lint

lint-fix: $(NODE_MODULES)
	npm run lint:fix

format: $(NODE_MODULES)
	npm run format

typecheck: $(NODE_MODULES)
	npm run typecheck

test: $(NODE_MODULES)
	npm run api-types:check
	npm test -- --ci

api-types: $(NODE_MODULES)
	npm run api-types

build: $(NODE_MODULES)
	npm run export

run: $(NODE_MODULES)
	npx expo start --port $(RUN_PORT)

eas-build-dev: $(NODE_MODULES)
	npx eas-cli@latest build --profile development --platform all

eas-build-preview: $(NODE_MODULES)
	npx eas-cli@latest build --profile preview --platform all

up logs:
	@echo "mobile-plusdas runs on phones, not in Docker: use 'make run' (Metro) or an EAS build"

down down-all:
	@true

clean:
	rm -rf dist .expo
