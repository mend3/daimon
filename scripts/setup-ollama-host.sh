#!/usr/bin/env bash
# Run this ON THE macOS HOST (not inside the devcontainer).
# Installs Ollama natively (Metal GPU), exposes it to the container, and pulls
# the default model with a 64K serving context (Hermes Agent's minimum).
set -euo pipefail

MODEL="${1:-gpt-oss:20b}"

# Exposed to the container via host.docker.internal, on a 64K window. q8_0 KV
# cache + flash attention keep the context within unified memory.
export OLLAMA_HOST="0.0.0.0:11434"
export OLLAMA_CONTEXT_LENGTH="65536"
export OLLAMA_FLASH_ATTENTION="1"
export OLLAMA_KV_CACHE_TYPE="q8_0"

echo "==> Ensuring Ollama is installed"
if ! command -v ollama >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    # The desktop app cask bundles the Metal-accelerated runner.
    brew install --cask ollama-app
  else
    echo "    Homebrew not found. Install Ollama from https://ollama.com/download"
    echo "    then re-run this script."
    exit 1
  fi
fi

# Persist the settings so the Ollama menubar app inherits them too.
echo "==> Applying Ollama settings (login session)"
for var in OLLAMA_HOST OLLAMA_CONTEXT_LENGTH OLLAMA_FLASH_ATTENTION OLLAMA_KV_CACHE_TYPE; do
  launchctl setenv "${var}" "${!var}" || true
done

# Stable log location the monitoring stack (Promtail) reads.
LOG_DIR="${HOME}/.hermes-monitoring"
mkdir -p "${LOG_DIR}"

echo "==> Pulling model: ${MODEL}"
if ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "    Starting 'ollama serve' in the background..."
  nohup ollama serve >"${LOG_DIR}/ollama.log" 2>&1 &
  sleep 3
fi
ollama pull "${MODEL}"

echo ""
echo "==> Done. Serving http://0.0.0.0:11434 with '${MODEL}' (64K context)."
echo "    Keep it running while you use the devcontainer."
echo ""
echo "    Using the Ollama menubar app instead of this script? The settings above"
echo "    are applied to the login session via launchctl; quit and reopen the app"
echo "    so it picks them up."
