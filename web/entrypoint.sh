#!/bin/sh
# Load Ella's secrets (QDRANT_API_KEY, MINIFLUX_*, TELEGRAM_BOT_TOKEN) and config
# from the mounted hermes-data volume, then start the web server. Same approach as
# the MCP launcher — works regardless of how env is otherwise passed.
set -e
if [ -f "${HOME}/.hermes/.env" ]; then
  set -a; . "${HOME}/.hermes/.env"; set +a
fi
export ELLA_KB_CONFIG="${ELLA_KB_CONFIG:-${HOME}/.hermes/ella_kb.yaml}"
exec ella-web
