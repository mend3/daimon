#!/usr/bin/env bash
# Run this ON THE macOS HOST. Starts the Grafana + Loki + Promtail stack that
# streams Hermes, Ollama, and SearXNG logs to http://localhost:3000.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../monitoring"

# Promtail reads the Ollama log from here; make sure it exists before it mounts.
mkdir -p "${HOME}/.hermes-monitoring"

# Generate the Telegram alert contact point from .env (token stays out of git).
CP_DIR="grafana/provisioning/alerting"
if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    sed -e "s|__TELEGRAM_BOT_TOKEN__|${TELEGRAM_BOT_TOKEN}|" \
        -e "s|__TELEGRAM_CHAT_ID__|${TELEGRAM_CHAT_ID}|" \
        "${CP_DIR}/contactpoints.yaml.example" > "${CP_DIR}/contactpoints.yaml"
    echo "==> Telegram alert contact point generated"
  fi
else
  echo "==> No monitoring/.env — alerts will have no Telegram contact point"
fi

echo "==> Starting monitoring stack"
docker compose up -d

echo "==> Waiting for Grafana"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 http://localhost:3000/api/health >/dev/null 2>&1; then
    echo "    OK - Grafana up at http://localhost:3000 (dashboard: Hermes — Live Activity)"
    exit 0
  fi
  sleep 2
done

echo "    WARN - Grafana did not answer in time. Check: docker logs hermes-grafana"
exit 1
