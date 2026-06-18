# Hermes Agent — local setup. Host-side targets wrap scripts/; see README.md.
.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help up doctor ollama searxng tts web monitoring services firewall devcontainer backup down

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n",$$1,$$2}'

up: searxng tts ## Bring up Ella's sidecars on the host (oracle provides shared infra)
	@echo "Host ready. Bring up oracle first (creates the 'workspace' network + globals: redis/qdrant/ollama/postgres + observability). Then open the devcontainer (VS Code: Reopen in Container) and run 'hermes'."

doctor: ## Check host services and models are reachable (preflight)
	./scripts/doctor.sh

ollama: ## Install host Ollama + pull vision/embedding models (chat model served by oracle's ollama)
	./scripts/setup-ollama-host.sh
	ollama pull qwen2.5vl:7b
	ollama pull nomic-embed-text

searxng: ## Start SearXNG (uses oracle's redis over the workspace network)
	./scripts/setup-searxng-host.sh

tts: ## Start the local TTS engine for voice replies (127.0.0.1:8880)
	./scripts/setup-tts-host.sh

web: ## Build + serve Ella's web canvas on 127.0.0.1:8099 (no local npm needed)
	./scripts/setup-web-host.sh

monitoring: ## Start the app-level telemetry sidecars (chat-shipper + status-exporter)
	docker compose --profile monitoring up -d

services: ## Install launchd agents (managed Ollama, autostart, daily backup)
	./scripts/install-host-services.sh

firewall: ## Block Ollama/SearXNG on the LAN, persisted across reboots (sudo)
	sudo ./scripts/install-firewall-daemon.sh

devcontainer: ## Build and start the devcontainer (needs @devcontainers/cli)
	devcontainer up --workspace-folder .

backup: ## Back up the hermes-data volume to ~/hermes-backups (Qdrant lives in oracle)
	./scripts/backup-hermes.sh

# Miniflux now runs in oracle (oracle/vendors/miniflux.compose.yml), consumed at
# host.docker.internal:8930 (or miniflux:8080 on `workspace`) — no `make miniflux` here.

down: ## Stop Ella's host docker stacks (shared infra is owned by oracle)
	-docker compose --profile core --profile web --profile monitoring down
