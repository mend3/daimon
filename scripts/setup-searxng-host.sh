#!/usr/bin/env bash
# Starts SearXNG for Hermes' web search, reachable on the shared network at
# daimon-searxng:8080 (and http://localhost:8888 from the host). Its cache/limiter uses
# the shared Redis over that network (DNS `redis:6379`, db 5) — start your shared infra
# stack first.
#
# settings.yml is generated (it holds a secret) and gitignored, so it must exist before
# any `docker compose up` of searxng, including one driven from outside this Makefile.
# That is what `make settings` is for.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

./scripts/setup-searxng-settings.sh

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
