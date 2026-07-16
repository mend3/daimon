#!/usr/bin/env bash
# Runs on every container start, from the entrypoint, before the gateway.
# Idempotent: installs Hermes only when missing, then syncs config from the repo.
set -euo pipefail

HERMES_HOME="${HOME}/.hermes"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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

# Claude Code CLI — installs to ~/.local/bin (the persisted volume), so rebuilds
# skip it after the first install.
if ! command -v claude >/dev/null 2>&1; then
  echo "==> Installing Claude Code (CLI)..."
  curl -fsSL https://claude.ai/install.sh | bash
else
  echo "==> Claude Code already installed: $(command -v claude)"
fi

# Web dashboard deps — install.sh installs Hermes CLI-only, so the dashboard's
# FastAPI/Uvicorn (web) and ptyprocess (pty) extras must be added separately.
echo "==> Ensuring web dashboard extras"
"${VENV_PIP}" install -q 'hermes-agent[web,pty]' 2>/dev/null || true

# Voice transcription (Telegram voice messages) — Hermes' local STT backend.
echo "==> Ensuring faster-whisper (voice)"
"${VENV_PIP}" install -q faster-whisper 2>/dev/null || true

# Daimon's knowledge base + workflow engine — install into the Hermes venv so the
# daimon-kb MCP server and the CLI are available. Editable so repo edits take effect;
# extras pull the MCP server and feed parsing.
echo "==> Installing daimon_kb / daimon_flow"
"${VENV_PIP}" install -q -e "${REPO_ROOT}/ingestion[mcp,feeds]" 2>/dev/null \
  || echo "    WARN - daimon package install failed; check ${REPO_ROOT}/ingestion"

# Make /help command listings tappable in Telegram (idempotent). Non-fatal, but a
# non-zero exit means the patch couldn't apply (Hermes layout changed) — surface it
# instead of silently dropping the feature.
echo "==> Patching Telegram help for clickable commands"
if ! "${HOME}/.hermes/hermes-agent/venv/bin/python" \
    "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/patches/telegram-help-clickable.py"; then
  echo "    WARN - clickable-commands patch did not apply; /help commands won't be" \
       "tappable in Telegram. Check docker/agent/patches/telegram-help-clickable.py" \
       "against the installed Hermes."
fi

# 2. Sync the version-controlled config into ~/.hermes.
#    config.yaml is always overwritten from the repo (it is the source of truth);
#    .env is seeded from the example only if absent, so local secrets survive.
echo "==> Syncing configuration"
cp "${REPO_CONFIG_DIR}/config.yaml" "${HERMES_HOME}/config.yaml"
cp "${REPO_CONFIG_DIR}/SOUL.md" "${HERMES_HOME}/SOUL.md"
cp "${REPO_CONFIG_DIR}/daimon_kb.yaml" "${HERMES_HOME}/daimon_kb.yaml"
install -m 0755 "$(dirname "${BASH_SOURCE[0]}")/daimon-kb-mcp.sh" "${HERMES_HOME}/daimon-kb-mcp.sh"
if [ ! -f "${HERMES_HOME}/.env" ]; then
  cp "${REPO_CONFIG_DIR}/.env.example" "${HERMES_HOME}/.env"
fi

# Gateway session policy (e.g. Telegram idle reset). Seeded if absent so the
# gateway's own runtime fields aren't clobbered; edit ~/.hermes/gateway.json (or
# delete it to re-seed) to change.
if [ ! -f "${HERMES_HOME}/gateway.json" ]; then
  cp "${REPO_CONFIG_DIR}/gateway.json" "${HERMES_HOME}/gateway.json"
fi

# Daimon's skills (each becomes a /command). Mirror the repo copies, which are the
# source of truth, into the runtime skills dir.
if [ -d "${REPO_CONFIG_DIR}/skills" ]; then
  echo "==> Syncing skills"
  mkdir -p "${HERMES_HOME}/skills"
  cp -R "${REPO_CONFIG_DIR}/skills/." "${HERMES_HOME}/skills/"
fi

# Named profiles (config/profiles/*) — each a separate Hermes home for an alternate
# model backend: `ollama` (local) and `claude` (your subscription). Their isolated
# .env gets the Telegram creds (so task agents can `hermes send`) plus any provider
# auth the profile needs. The default profile (above) is OpenAI gpt-5.5.
for pdir in "${REPO_CONFIG_DIR}"/profiles/*/; do
  [ -f "${pdir}config.yaml" ] || continue
  pname="$(basename "${pdir}")"
  echo "==> Syncing profile: ${pname}"
  hermes profile create "${pname}" </dev/null >/dev/null 2>&1 || true
  PDIR="${HERMES_HOME}/profiles/${pname}"
  mkdir -p "${PDIR}"
  cp "${pdir}config.yaml" "${PDIR}/config.yaml"
  touch "${PDIR}/.env"
  grep -vE "^(TELEGRAM_|CLAUDE_CODE_OAUTH_TOKEN=)" "${PDIR}/.env" > "${PDIR}/.env.tmp" 2>/dev/null || true
  grep -E "^TELEGRAM_" "${HERMES_HOME}/.env" >> "${PDIR}/.env.tmp" 2>/dev/null || true
  # The anthropic provider resolves its OAuth from CLAUDE_CODE_OAUTH_TOKEN in the env.
  [ "${pname}" = "claude-max" ] && grep -E "^CLAUDE_CODE_OAUTH_TOKEN=" "${HERMES_HOME}/.env" >> "${PDIR}/.env.tmp" 2>/dev/null || true
  mv "${PDIR}/.env.tmp" "${PDIR}/.env"
done

# The OpenAI fallback (config.yaml: openai-api / gpt-5-mini) reads OPENAI_API_KEY /
# OPENAI_BASE_URL from the env, which the container points at the local Ollama — so
# override them in ~/.hermes/.env (loaded with precedence) from the single
# user-facing key OPENAI_PROFILE_API_KEY. Taken from the environment when the file
# has none, so the key can live in the repo .env that compose already reads.
# Optional: the primary model is local, so without a key the fallback is simply
# unavailable — say so instead of failing.
DK="$(sed -n 's/^OPENAI_PROFILE_API_KEY=//p' "${HERMES_HOME}/.env" | head -1)"
DK="${DK:-${OPENAI_PROFILE_API_KEY:-}}"
if [ -n "${DK}" ]; then
  grep -vE "^(OPENAI_API_KEY|OPENAI_BASE_URL)=" "${HERMES_HOME}/.env" \
    > "${HERMES_HOME}/.env.tmp" 2>/dev/null || true
  {
    echo "OPENAI_API_KEY=${DK}"
    echo "OPENAI_BASE_URL=https://api.openai.com/v1"
  } >> "${HERMES_HOME}/.env.tmp"
  mv "${HERMES_HOME}/.env.tmp" "${HERMES_HOME}/.env"
else
  echo "    NOTE - OPENAI_PROFILE_API_KEY unset; running local-only. The OpenAI" \
       "fallback is unavailable, so an Ollama outage takes Daimon with it."
fi

# Claude Code OAuth token in interactive shells — the `claude` CLI authenticates
# only from CLAUDE_CODE_OAUTH_TOKEN in its process env (no headless credential file),
# so export it from ~/.hermes/.env for interactive shells and the dashboard launched
# from one. Hermes' launcher sanitizes its own env, so this does not affect it.
BASHRC="${HOME}/.bashrc"
if [ -f "${BASHRC}" ] && ! grep -qF "# daimon: Claude Code OAuth token" "${BASHRC}"; then
  echo "==> Adding Claude Code token export to ~/.bashrc"
  cat >> "${BASHRC}" <<'EOF'

# daimon: Claude Code OAuth token — export from ~/.hermes/.env for the claude CLI.
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -f "$HOME/.hermes/.env" ]; then
  _cct=$(sed -n 's/^CLAUDE_CODE_OAUTH_TOKEN=//p' "$HOME/.hermes/.env" | head -1)
  [ -n "$_cct" ] && export CLAUDE_CODE_OAUTH_TOKEN="$_cct"; unset _cct
fi
EOF
fi

# Proactivity: a daily morning briefing (Daimon's signature is anticipation). Created
# only when Telegram is configured and the job is absent (idempotent). Schedule is in
# the config timezone (UTC by default). Pause/remove with `hermes cron pause|remove`.
if grep -qE "^TELEGRAM_BOT_TOKEN=.+" "${HERMES_HOME}/.env" 2>/dev/null \
   && ! hermes cron list 2>/dev/null | grep -q "morning-briefing"; then
  echo "==> Creating morning-briefing cron job"
  hermes cron create "0 8 * * *" \
    "Bom dia. Faça um briefing curto de início de dia, no seu tom natural e conciso (é mensagem de chat): o que está pendente no quadro kanban (cheque com as ferramentas do kanban), qualquer coisa que eu tenha sinalizado, e uma coisa que valha minha atenção hoje. Se nada for relevante, uma saudação breve basta." \
    --name "morning-briefing" --deliver telegram --profile default >/dev/null 2>&1 \
    || echo "    NOTE - could not create morning-briefing cron job"
fi

# 3. Quick reachability check against the shared Ollama (non-fatal).
echo "==> Checking Ollama at ollama:11434"
if curl -fsS --max-time 3 http://ollama:11434/api/tags >/dev/null 2>&1; then
  echo "    OK - Ollama is reachable."
else
  echo "    WARN - Ollama not reachable. It belongs to your shared infra stack —"
  echo "           start it on the shared network, then rebuild this container."
fi

echo "==> setup done. Run 'hermes' to start chatting."
