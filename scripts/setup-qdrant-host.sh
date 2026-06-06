#!/usr/bin/env bash
# Run on the macOS HOST. Starts Qdrant (Ella's knowledge-base vector store) on
# 127.0.0.1:6333 and the `hermes-shared` Docker network. The devcontainer reaches
# it at host.docker.internal:6333 with the API key from qdrant/.env.
#
# After first run, copy the generated key into ~/.hermes/.env as QDRANT_API_KEY so
# Ella can connect (the script prints a reminder).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../qdrant"

if [ ! -f .env ]; then
  echo "==> Generating qdrant/.env with a fresh API key"
  sed "s|QDRANT_API_KEY=|QDRANT_API_KEY=$(openssl rand -hex 24)|" .env.example > .env
fi

echo "==> Starting Qdrant"
docker compose up -d

KEY="$(grep '^QDRANT_API_KEY=' .env | cut -d= -f2)"

echo "==> Waiting for Qdrant"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 -H "api-key: ${KEY}" http://localhost:6333/readyz >/dev/null 2>&1; then
    echo "    OK - Qdrant ready on 127.0.0.1:6333 (network: hermes-shared)"
    echo "    Add this to ~/.hermes/.env so Ella can connect:"
    echo "        QDRANT_API_KEY=${KEY}"
    exit 0
  fi
  sleep 2
done

echo "    WARN - Qdrant not ready in time. Check: docker logs hermes-qdrant"
exit 1
