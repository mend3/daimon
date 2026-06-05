#!/usr/bin/env bash
# Run this ON THE macOS HOST. Starts the Grafana + Loki + Promtail stack that
# streams Hermes, Ollama, and SearXNG logs to http://localhost:3000.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../monitoring"

# Promtail reads the Ollama log from here; make sure it exists before it mounts.
mkdir -p "${HOME}/.hermes-monitoring"

echo "==> Starting monitoring stack"
docker compose up -d

echo "==> Waiting for Grafana"
for i in $(seq 1 30); do
  if curl -fsS --max-time 3 http://localhost:3000/api/health >/dev/null 2>&1; then
    echo "    OK - Grafana up at http://localhost:3000 (dashboard: Hermes — Atividade ao vivo)"
    exit 0
  fi
  sleep 2
done

echo "    WARN - Grafana did not answer in time. Check: docker logs hermes-grafana"
exit 1
