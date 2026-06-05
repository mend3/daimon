#!/usr/bin/env bash
# Runs once after the container is created (and again after rebuilds).
# Idempotent: installs Hermes only when missing, then syncs config from the repo.
set -euo pipefail

HERMES_HOME="${HOME}/.hermes"
REPO_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config"

echo "==> Preparing ${HERMES_HOME}"
# The named volume mounts empty and root-owned; hand it to the runtime user.
if [ ! -w "${HERMES_HOME}" ]; then
  sudo chown -R vscode:vscode "${HERMES_HOME}"
fi
mkdir -p "${HERMES_HOME}"

# 1. Install Hermes Agent (CLI-only) if the launcher is not present.
#    The launcher lives in ~/.local/bin which is not on the persisted volume,
#    so this re-runs after a full rebuild and restores it.
if ! command -v hermes >/dev/null 2>&1; then
  echo "==> Installing Hermes Agent (CLI)..."
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
else
  echo "==> Hermes already installed: $(command -v hermes)"
fi

# 2. Sync the version-controlled config into ~/.hermes.
#    config.yaml is always overwritten from the repo (it is the source of truth);
#    .env is seeded from the example only if absent, so local secrets survive.
echo "==> Syncing configuration"
cp "${REPO_CONFIG_DIR}/config.yaml" "${HERMES_HOME}/config.yaml"
cp "${REPO_CONFIG_DIR}/SOUL.md" "${HERMES_HOME}/SOUL.md"
if [ ! -f "${HERMES_HOME}/.env" ]; then
  cp "${REPO_CONFIG_DIR}/.env.example" "${HERMES_HOME}/.env"
fi

# 3. Quick reachability check against the host Ollama endpoint (non-fatal).
echo "==> Checking Ollama at host.docker.internal:11434"
if curl -fsS --max-time 3 http://host.docker.internal:11434/api/tags >/dev/null 2>&1; then
  echo "    OK - Ollama is reachable."
else
  echo "    WARN - Ollama not reachable yet. On the macOS host run:"
  echo "           OLLAMA_HOST=0.0.0.0:11434 ollama serve   (+ ollama pull qwen3:8b)"
  echo "           See scripts/setup-ollama-host.sh"
fi

echo "==> postCreate done. Run 'hermes' to start chatting."
