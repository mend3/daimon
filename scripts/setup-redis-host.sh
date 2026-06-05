#!/usr/bin/env bash
# Run on the macOS HOST. Starts a shared, password-protected Redis on
# 127.0.0.1:6379 and the `hermes-shared` Docker network.
#
# Use it from another container: add `networks: [hermes-shared]` (external) to
# its compose and connect to redis:6379 with the password from redis/.env.
# Use it from the host/CLI: redis-cli -a "$REDIS_PASSWORD" -h 127.0.0.1
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../redis"

if [ ! -f .env ]; then
  echo "==> Generating redis/.env with a fresh password"
  sed "s|REDIS_PASSWORD=|REDIS_PASSWORD=$(openssl rand -hex 24)|" .env.example > .env
fi

echo "==> Starting Redis"
docker compose up -d

echo "==> Waiting for Redis"
for _ in $(seq 1 15); do
  if [ "$(docker inspect -f '{{.State.Health.Status}}' hermes-redis 2>/dev/null)" = "healthy" ]; then
    echo "    OK - Redis healthy on 127.0.0.1:6379 (network: hermes-shared)"
    exit 0
  fi
  sleep 2
done

echo "    WARN - Redis not healthy in time. Check: docker logs hermes-redis"
exit 1
