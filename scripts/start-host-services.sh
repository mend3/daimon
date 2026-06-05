#!/usr/bin/env bash
# Brings up the host Docker stacks (SearXNG + monitoring). Run by the
# com.hermes.stacks LaunchAgent at login, after waiting for Docker to be ready.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Docker Desktop may still be starting at login — wait up to ~3 min.
for _ in $(seq 1 90); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done
docker info >/dev/null 2>&1 || { echo "docker not ready; giving up"; exit 0; }

docker compose -f "${REPO}/searxng/docker-compose.yml" up -d || true
docker compose -f "${REPO}/monitoring/docker-compose.yml" up -d || true
[ -f "${REPO}/redis/.env" ] && docker compose -f "${REPO}/redis/docker-compose.yml" up -d || true
