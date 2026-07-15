#!/usr/bin/env bash
# Generate docker/searxng/settings.yml from the example, injecting a fresh secret_key.
# Idempotent: an existing file is left alone (regenerate by deleting it first).
#
# The file is gitignored, so a fresh clone has none — and the searxng service bind-mounts
# it. Without this, Docker would create a *directory* at that path and searxng would fail
# to start. Run it before bringing searxng up by any route.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ -f docker/searxng/settings.yml ]; then
  exit 0
fi

echo "==> Generating docker/searxng/settings.yml with a fresh secret"
cp docker/searxng/settings.yml.example docker/searxng/settings.yml
secret="$(openssl rand -hex 32)"
sed -i.bak "s/GENERATE_ME/${secret}/" docker/searxng/settings.yml
rm -f docker/searxng/settings.yml.bak
