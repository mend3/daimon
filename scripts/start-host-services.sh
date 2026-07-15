#!/usr/bin/env bash
# Brings up Daimon's host Docker stacks (SearXNG + TTS + telemetry sidecars). Run by
# the com.hermes.stacks LaunchAgent at login, after waiting for Docker to be ready.
# Shared infra (redis/qdrant/ollama/observability) is provided by your own stack on
# the external `shared` Docker network — start it first (e.g. `docker network create shared`).
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Docker Desktop may still be starting at login — wait up to ~3 min.
for _ in $(seq 1 90); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done
docker info >/dev/null 2>&1 || { echo "docker not ready; giving up"; exit 0; }

# Core sidecars: SearXNG's cache/limiter uses the shared Redis on `shared` (db 5).
docker compose -f "${REPO}/docker-compose.yml" up -d searxng tts || true
# App-level telemetry sidecars (chat-shipper + status-exporter) ship to the shared
# observability plane over `shared`.
docker compose -f "${REPO}/docker-compose.yml" --profile monitoring up -d || true
