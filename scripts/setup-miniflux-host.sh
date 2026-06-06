#!/usr/bin/env bash
# Run on the macOS HOST. Starts Miniflux (feed reader) + its Postgres on
# 127.0.0.1:8930 and the `hermes-shared` Docker network. Ella's `feeds` adapter
# reaches the API at host.docker.internal:8930 using the admin credentials.
#
# After first run, mirror the credentials into ~/.hermes/.env (the script prints
# them) and enable the `feeds` capability in config/ella_kb.yaml.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../miniflux"

if [ ! -f .env ]; then
  echo "==> Generating miniflux/.env with fresh secrets"
  sed -e "s|POSTGRES_PASSWORD=|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" \
      -e "s|MINIFLUX_ADMIN_PASSWORD=|MINIFLUX_ADMIN_PASSWORD=$(openssl rand -hex 16)|" \
      .env.example > .env
fi

echo "==> Starting Miniflux + Postgres"
docker compose up -d

echo "==> Waiting for Miniflux"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 http://localhost:8930/healthcheck >/dev/null 2>&1; then
    USER="$(grep '^MINIFLUX_ADMIN_USERNAME=' .env | cut -d= -f2)"
    PASS="$(grep '^MINIFLUX_ADMIN_PASSWORD=' .env | cut -d= -f2)"
    echo "    OK - Miniflux up on http://localhost:8930 (network: hermes-shared)"
    echo "    Add these to ~/.hermes/.env so Ella can read feeds:"
    echo "        MINIFLUX_URL=http://host.docker.internal:8930"
    echo "        MINIFLUX_USERNAME=${USER}"
    echo "        MINIFLUX_PASSWORD=${PASS}"
    exit 0
  fi
  sleep 2
done

echo "    WARN - Miniflux not healthy in time. Check: docker logs hermes-miniflux"
exit 1
