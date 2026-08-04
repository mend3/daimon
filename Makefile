# Daimon — local setup. Targets wrap scripts/; see README.md.
#
# The shared infra (Ollama, Qdrant, Redis, observability) comes from your own stack on an
# external Docker network. Start it first, then bring up Daimon's own sidecars here.
.DEFAULT_GOAL := help
SHELL := /bin/bash

# Local overrides, if you keep any (gitignored). Read before the defaults below so a
# value set here wins without being passed on every command line — a `doctor` that
# reports a broken stack because you forgot an env var is worse than no doctor.
-include .env
export

# Name of that external network. Daimon's sidecars, the devcontainer and `make doctor`
# all join it, so it is exported to every child process (compose, devcontainer CLI).
#   make up SHARED_NETWORK=my-net   (or set it once in .env)
SHARED_NETWORK ?= shared
export SHARED_NETWORK

.PHONY: help up agent volumes doctor monitoring services devcontainer backup down

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n",$$1,$$2}'

up: agent ## Bring up Daimon (shared infra — incl. search and voice — comes from your own stack)
	@echo "Daimon up. Talk to him on your messaging gateway, or 'docker compose exec agent hermes'. Logs: 'docker compose logs -f agent'."

# Declared external in compose (the devcontainer mounts them by the same name), so
# compose won't create them — but `docker volume create` is idempotent and cheap.
volumes: ## Create the named volumes Hermes' home and toolchain persist in
	@docker volume create hermes-data >/dev/null
	@docker volume create hermes-local >/dev/null

agent: volumes ## Start Daimon himself (the container Hermes runs in)
	docker compose --profile core up -d --build agent

doctor: ## Check the services and models Daimon depends on (preflight)
	./scripts/doctor.sh

monitoring: ## Start the app-level telemetry sidecars (chat-shipper + status-exporter)
	docker compose --profile monitoring up -d

services: ## Install launchd agents (autostart, daily backup) — macOS host only
	./scripts/install-host-services.sh

devcontainer: volumes ## Build and start the dev container for editing this repo (needs @devcontainers/cli)
	devcontainer up --workspace-folder .

backup: ## Back up the hermes-data volume to ~/hermes-backups (Qdrant lives in your shared stack)
	./scripts/backup-hermes.sh

# Ollama is part of your shared stack, not Daimon's to install — pull the models Daimon
# needs (see `make doctor`) there. Miniflux (optional feeds source) likewise: point
# MINIFLUX_URL at your own.

down: ## Stop Daimon's sidecars (your shared stack stays up)
	-docker compose --profile core --profile monitoring down
