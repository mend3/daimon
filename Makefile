# Hermes Agent — local setup. Host-side targets wrap scripts/; see README.md.
.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help up doctor ollama redis searxng tts qdrant miniflux web monitoring services firewall devcontainer backup down

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n",$$1,$$2}'

up: ollama redis searxng tts qdrant monitoring ## Bring up everything on the host
	@echo "Host ready. Open the devcontainer (VS Code: Reopen in Container) and run 'hermes'."

doctor: ## Check host services and models are reachable (preflight)
	./scripts/doctor.sh

ollama: ## Install Ollama + pull the chat, vision, and embedding models
	./scripts/setup-ollama-host.sh
	ollama pull qwen2.5vl:7b
	ollama pull nomic-embed-text

redis: ## Start the shared Redis
	./scripts/setup-redis-host.sh

searxng: redis ## Start SearXNG (uses Redis)
	./scripts/setup-searxng-host.sh

tts: ## Start the local TTS engine for voice replies (127.0.0.1:8880)
	./scripts/setup-tts-host.sh

qdrant: ## Start Qdrant, the knowledge-base vector store (127.0.0.1:6333)
	./scripts/setup-qdrant-host.sh

miniflux: ## Start Miniflux feed reader for the feeds connector (127.0.0.1:8930)
	./scripts/setup-miniflux-host.sh

web: ## Build + serve Ella's web canvas on 127.0.0.1:8099 (no local npm needed)
	./scripts/setup-web-host.sh

monitoring: ## Start Grafana/Loki/Prometheus on localhost:3000
	./scripts/setup-monitoring-host.sh

services: ## Install launchd agents (managed Ollama, autostart, daily backup)
	./scripts/install-host-services.sh

firewall: ## Block Ollama/SearXNG on the LAN, persisted across reboots (sudo)
	sudo ./scripts/install-firewall-daemon.sh

devcontainer: ## Build and start the devcontainer (needs @devcontainers/cli)
	devcontainer up --workspace-folder .

backup: ## Back up the hermes-data and Qdrant volumes to ~/hermes-backups
	./scripts/backup-hermes.sh
	./scripts/backup-qdrant-host.sh

down: ## Stop the host docker stacks
	-docker compose -f monitoring/docker-compose.yml down
	-docker compose -f web/docker-compose.yml down
	-docker compose -f miniflux/docker-compose.yml down
	-docker compose -f qdrant/docker-compose.yml down
	-docker compose -f tts/docker-compose.yml down
	-docker compose -f searxng/docker-compose.yml down
	-docker compose -f redis/docker-compose.yml down
