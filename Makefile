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

.PHONY: help up doctor settings searxng tts monitoring services firewall devcontainer backup down

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n",$$1,$$2}'

up: searxng tts ## Bring up Daimon's sidecars (shared infra comes from your own stack)
	@echo "Sidecars up. Start your shared infra stack (Redis/Qdrant/Ollama + observability) on the network named by SHARED_NETWORK, then open the devcontainer (VS Code: Reopen in Container, or 'make devcontainer') and run 'hermes'."

doctor: ## Check the services and models Daimon depends on (preflight)
	./scripts/doctor.sh

settings: ## Generate docker/searxng/settings.yml (gitignored; needed before any compose up)
	./scripts/setup-searxng-settings.sh

searxng: settings ## Start SearXNG (uses the shared Redis over the shared network)
	./scripts/setup-searxng-host.sh

tts: ## Start the local TTS engine for voice replies (127.0.0.1:8880)
	./scripts/setup-tts-host.sh

monitoring: ## Start the app-level telemetry sidecars (chat-shipper + status-exporter)
	docker compose --profile monitoring up -d

services: ## Install launchd agents (autostart, daily backup) — macOS host only
	./scripts/install-host-services.sh

firewall: ## Block SearXNG on the LAN, persisted across reboots (macOS host only, sudo)
	sudo ./scripts/install-firewall-daemon.sh

devcontainer: ## Build and start the devcontainer (needs @devcontainers/cli)
	devcontainer up --workspace-folder .

backup: ## Back up the hermes-data volume to ~/hermes-backups (Qdrant lives in your shared stack)
	./scripts/backup-hermes.sh

# Ollama is part of your shared stack, not Daimon's to install — pull the models Daimon
# needs (see `make doctor`) there. Miniflux (optional feeds source) likewise: point
# MINIFLUX_URL at your own.

down: ## Stop Daimon's sidecars (your shared stack stays up)
	-docker compose --profile core --profile monitoring down
