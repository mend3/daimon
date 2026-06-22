#!/usr/bin/env bash
# Run this ON THE macOS HOST. Starts a local SearXNG for Hermes' web search,
# reachable from the devcontainer at host.docker.internal:8888. Its cache/limiter
# uses oracle's Redis on the external `workspace` network (DNS `redis:6379`, db 5)
# — bring up oracle first: `cd ../../foundation/oracle && make up`.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -f docker/searxng/settings.yml ]; then
  echo "==> Generating settings.yml with a fresh secret"
  cp docker/searxng/settings.yml.example docker/searxng/settings.yml
  sed -i '' "s/GENERATE_ME/$(openssl rand -hex 32)/" docker/searxng/settings.yml
fi

echo "==> Starting SearXNG"
docker compose up -d searxng

echo "==> Waiting for the JSON API"
for _ in $(seq 1 20); do
  if curl -fsS --max-time 3 "http://localhost:8888/search?q=test&format=json" >/dev/null 2>&1; then
    echo "    OK - SearXNG JSON API is up on http://localhost:8888"
    exit 0
  fi
  sleep 2
done

echo "    WARN - SearXNG did not answer in time. Check: docker logs hermes-searxng"
exit 1
