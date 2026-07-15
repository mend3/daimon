# Hermes Agent — local setup. Host-side targets wrap scripts/; see README.md.
.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help up doctor ollama searxng tts monitoring services firewall devcontainer backup down

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n",$$1,$$2}'

up: searxng tts ## Bring up Daimon's sidecars on the host (shared infra comes from your own stack)
	@echo "Host ready. Start your shared infra stack first (Redis/Qdrant/Ollama + observability on a Docker network named 'shared'). Then open the devcontainer (VS Code: Reopen in Container) and run 'hermes'."

doctor: ## Check host services and models are reachable (preflight)
	./scripts/doctor.sh

ollama: ## Install host Ollama + pull vision/embedding models (chat model served by your shared Ollama)
	./scripts/setup-ollama-host.sh
	ollama pull qwen2.5vl:7b
	ollama pull nomic-embed-text

searxng: ## Start SearXNG (uses the shared Redis over the `shared` network)
	./scripts/setup-searxng-host.sh

tts: ## Start the local TTS engine for voice replies (127.0.0.1:8880)
	./scripts/setup-tts-host.sh

monitoring: ## Start the app-level telemetry sidecars (chat-shipper + status-exporter)
	docker compose --profile monitoring up -d

services: ## Install launchd agents (managed Ollama, autostart, daily backup)
	./scripts/install-host-services.sh

firewall: ## Block Ollama/SearXNG on the LAN, persisted across reboots (sudo)
	sudo ./scripts/install-firewall-daemon.sh

devcontainer: ## Build and start the devcontainer (needs @devcontainers/cli)
	devcontainer up --workspace-folder .

backup: ## Back up the hermes-data volume to ~/hermes-backups (Qdrant lives in your shared stack)
	./scripts/backup-hermes.sh

# Miniflux (optional feeds source) is expected on your shared stack, consumed at
# host.docker.internal:8930 (or miniflux:8080 on `shared`) — no `make miniflux` here.

down: ## Stop Daimon's host docker stacks (shared infra is provided by your own stack)
	-docker compose --profile core --profile monitoring down
