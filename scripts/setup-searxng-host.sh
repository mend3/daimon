#!/usr/bin/env bash
# Run this ON THE macOS HOST. Starts a local SearXNG for Hermes' web search,
# reachable from the devcontainer at host.docker.internal:8080.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../searxng"

if [ ! -f settings.yml ]; then
  echo "==> Generating settings.yml with a fresh secret"
  cp settings.yml.example settings.yml
  secret="$(openssl rand -hex 32)"
  sed -i '' "s/GENERATE_ME/${secret}/" settings.yml
fi

echo "==> Starting SearXNG"
docker compose up -d

echo "==> Waiting for the JSON API"
for i in $(seq 1 20); do
  if curl -fsS --max-time 3 "http://localhost:8888/search?q=test&format=json" >/dev/null 2>&1; then
    echo "    OK - SearXNG JSON API is up on http://localhost:8888"
    exit 0
  fi
  sleep 2
done

echo "    WARN - SearXNG did not answer in time. Check: docker logs hermes-searxng"
exit 1
