#!/usr/bin/env bash
# Launches the knowledge-base MCP server for Hermes. Loads ~/.hermes/.env first so
# the server gets QDRANT_API_KEY regardless of how Hermes passes env to MCP
# subprocesses, then execs it in the Hermes venv (where daimon_kb is installed).
set -euo pipefail

set -a
[ -f "${HOME}/.hermes/.env" ] && . "${HOME}/.hermes/.env"
set +a

export DAIMON_KB_CONFIG="${DAIMON_KB_CONFIG:-${HOME}/.hermes/daimon_kb.yaml}"
exec "${HOME}/.hermes/hermes-agent/venv/bin/python" -m daimon_kb.apps.mcp_server
