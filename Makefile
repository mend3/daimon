# Hermes Agent — local setup. Host-side targets wrap scripts/; see README.md.
.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help up ollama redis searxng monitoring services firewall devcontainer backup down

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n",$$1,$$2}'

up: ollama redis searxng monitoring ## Bring up everything on the host
	@echo "Host ready. Open the devcontainer (VS Code: Reopen in Container) and run 'hermes'."

ollama: ## Install Ollama + pull the chat and vision models
	./scripts/setup-ollama-host.sh
	ollama pull qwen2.5vl:7b

redis: ## Start the shared Redis
	./scripts/setup-redis-host.sh

searxng: redis ## Start SearXNG (uses Redis)
	./scripts/setup-searxng-host.sh

monitoring: ## Start Grafana/Loki/Prometheus on localhost:3000
	./scripts/setup-monitoring-host.sh

services: ## Install launchd agents (managed Ollama, autostart, daily backup)
	./scripts/install-host-services.sh

firewall: ## Block Ollama/SearXNG on the LAN, persisted across reboots (sudo)
	sudo ./scripts/install-firewall-daemon.sh

devcontainer: ## Build and start the devcontainer (needs @devcontainers/cli)
	devcontainer up --workspace-folder .

backup: ## Back up the hermes-data volume to ~/hermes-backups
	./scripts/backup-hermes.sh

down: ## Stop the host docker stacks
	-docker compose -f monitoring/docker-compose.yml down
	-docker compose -f searxng/docker-compose.yml down
	-docker compose -f redis/docker-compose.yml down
