#!/usr/bin/env bash
# Runs once after the container is created (and again after rebuilds).
# Idempotent: installs Hermes only when missing, then syncs config from the repo.
set -euo pipefail

HERMES_HOME="${HOME}/.hermes"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_CONFIG_DIR="${REPO_ROOT}/config"
VENV_PIP="${HOME}/.hermes/hermes-agent/venv/bin/pip"

echo "==> Preparing persisted volumes"
# Named volumes mount empty and root-owned; hand them to the runtime user. Other
# containers that mount hermes-data (e.g. the web service) can leave files owned by
# another uid, so always reclaim ~/.hermes before syncing config into it.
mkdir -p "${HERMES_HOME}" 2>/dev/null || true
sudo chown -R vscode:vscode "${HERMES_HOME}" 2>/dev/null || true
mkdir -p "${HOME}/.local" 2>/dev/null || true
[ -w "${HOME}/.local" ] || sudo chown -R vscode:vscode "${HOME}/.local"

# 1. Install Hermes Agent (CLI-only) if not already present. The launcher and the
#    uv-managed Python both live in ~/.local (a persisted volume), so after the
#    first install rebuilds skip this entirely.
if ! command -v hermes >/dev/null 2>&1; then
  echo "==> Installing Hermes Agent (CLI)..."
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
else
  echo "==> Hermes already installed: $(command -v hermes)"
fi

# Voice transcription (Telegram voice messages) — Hermes' local STT backend.
echo "==> Ensuring faster-whisper (voice)"
"${VENV_PIP}" install -q faster-whisper 2>/dev/null || true

# Ella's knowledge base + workflow engine + web backend — install into the Hermes
# venv so the ella-kb MCP server, the CLI, and the ella-web server are available.
# Editable so repo edits take effect; extras pull MCP, feed parsing, and FastAPI.
echo "==> Installing ella_kb / ella_flow / ella_web"
"${VENV_PIP}" install -q -e "${REPO_ROOT}/ingestion[mcp,feeds,web]" 2>/dev/null \
  || echo "    WARN - ella package install failed; check ${REPO_ROOT}/ingestion"

# Make /help command listings tappable in Telegram (idempotent, non-fatal).
echo "==> Patching Telegram help for clickable commands"
"${HOME}/.hermes/hermes-agent/venv/bin/python" \
  "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/patches/telegram-help-clickable.py" || true

# 2. Sync the version-controlled config into ~/.hermes.
#    config.yaml is always overwritten from the repo (it is the source of truth);
#    .env is seeded from the example only if absent, so local secrets survive.
echo "==> Syncing configuration"
cp "${REPO_CONFIG_DIR}/config.yaml" "${HERMES_HOME}/config.yaml"
cp "${REPO_CONFIG_DIR}/SOUL.md" "${HERMES_HOME}/SOUL.md"
cp "${REPO_CONFIG_DIR}/ella_kb.yaml" "${HERMES_HOME}/ella_kb.yaml"
install -m 0755 "$(dirname "${BASH_SOURCE[0]}")/ella-kb-mcp.sh" "${HERMES_HOME}/ella-kb-mcp.sh"
if [ ! -f "${HERMES_HOME}/.env" ]; then
  cp "${REPO_CONFIG_DIR}/.env.example" "${HERMES_HOME}/.env"
fi

# Gateway session policy (e.g. Telegram idle reset). Seeded if absent so the
# gateway's own runtime fields aren't clobbered; edit ~/.hermes/gateway.json (or
# delete it to re-seed) to change.
if [ ! -f "${HERMES_HOME}/gateway.json" ]; then
  cp "${REPO_CONFIG_DIR}/gateway.json" "${HERMES_HOME}/gateway.json"
fi

# Ella's skills (each becomes a /command). Mirror the repo copies, which are the
# source of truth, into the runtime skills dir.
if [ -d "${REPO_CONFIG_DIR}/skills" ]; then
  echo "==> Syncing skills"
  mkdir -p "${HERMES_HOME}/skills"
  cp -R "${REPO_CONFIG_DIR}/skills/." "${HERMES_HOME}/skills/"
fi

# 3. Quick reachability check against the host Ollama endpoint (non-fatal).
echo "==> Checking Ollama at host.docker.internal:11434"
if curl -fsS --max-time 3 http://host.docker.internal:11434/api/tags >/dev/null 2>&1; then
  echo "    OK - Ollama is reachable."
else
  echo "    WARN - Ollama not reachable yet. On the macOS host run:"
  echo "           OLLAMA_HOST=0.0.0.0:11434 ollama serve   (+ ollama pull gpt-oss:20b)"
  echo "           See scripts/setup-ollama-host.sh"
fi

echo "==> postCreate done. Run 'hermes' to start chatting."
