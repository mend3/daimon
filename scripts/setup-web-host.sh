#!/usr/bin/env bash
# Run on the macOS HOST. Builds Ella's web layer (canvas + backend) and serves it on
# 127.0.0.1:8099 — no local Node/npm needed (the frontend builds inside Docker).
#
# Requires the hermes-data volume (run the devcontainer once first so Ella's config,
# SOUL, secrets, and knowledge ledger are populated and shared with the web service).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../web"

if ! docker volume inspect hermes-data >/dev/null 2>&1; then
  echo "ERROR: the hermes-data volume doesn't exist yet."
  echo "Open the devcontainer once (it syncs Ella's config), then re-run this."
  exit 1
fi

echo "==> Building + starting the web layer (first build compiles the frontend)"
docker compose up -d --build

echo "==> Waiting for the web server"
for _ in $(seq 1 40); do
  if curl -fsS --max-time 3 http://localhost:8099/api/health >/dev/null 2>&1; then
    echo "    OK - Ella's web canvas is up at http://localhost:8099"
    exit 0
  fi
  sleep 3
done

echo "    WARN - web server not healthy in time. Check: docker logs hermes-web"
exit 1
