#!/usr/bin/env bash
# Brings up Ella's host Docker stacks (SearXNG + TTS + telemetry sidecars). Run by
# the com.hermes.stacks LaunchAgent at login, after waiting for Docker to be ready.
# Shared infra (redis/qdrant/ollama/observability) is owned by oracle on the
# external `workspace` network — bring it up first: `cd ../oracle && make up`.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Docker Desktop may still be starting at login — wait up to ~3 min.
for _ in $(seq 1 90); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done
docker info >/dev/null 2>&1 || { echo "docker not ready; giving up"; exit 0; }

# Core sidecars: SearXNG's cache/limiter uses oracle's Redis on `workspace` (db 5).
docker compose -f "${REPO}/docker-compose.yml" up -d searxng tts || true
# App-level telemetry sidecars (chat-shipper + status-exporter) ship to oracle's
# observability plane over `workspace`.
docker compose -f "${REPO}/docker-compose.yml" --profile monitoring up -d || true
