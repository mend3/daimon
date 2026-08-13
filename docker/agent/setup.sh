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

# The hub owns Daimon's persona and serves it at GET /api/internal/persona;
# SOUL.md is just how Hermes loads one, so this writes the fetched text into the
# file Hermes reads. config/SOUL.md is the offline fallback. Downloads to a temp
# file and only then replaces the live one, so a truncated response never becomes
# the persona. A hub outage must not block startup.
fetch_soul() {
  if [ -z "${HUB_INTERNAL_URL:-}" ] || [ -z "${HUB_WORKER_TOKEN:-}" ]; then
    return 1
  fi
  curl -fsS --max-time 5 -H "x-internal-token: ${HUB_WORKER_TOKEN}" \
    "${HUB_INTERNAL_URL%/}/api/internal/persona" -o "${HERMES_HOME}/SOUL.md.tmp" \
    && [ -s "${HERMES_HOME}/SOUL.md.tmp" ]
}
if fetch_soul; then
  mv "${HERMES_HOME}/SOUL.md.tmp" "${HERMES_HOME}/SOUL.md"
  echo "    OK - SOUL synced from the hub"
else
  rm -f "${HERMES_HOME}/SOUL.md.tmp"
  cp "${REPO_CONFIG_DIR}/SOUL.md" "${HERMES_HOME}/SOUL.md"
  echo "    WARN - hub unreachable or HUB_INTERNAL_URL/HUB_WORKER_TOKEN unset;" \
       "using the repo SOUL.md fallback (may be stale)"
fi
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
# model backend or an alternate ROLE. Their isolated .env gets the Telegram creds (so
# task agents can `hermes send`) plus any provider auth the profile needs.
#
# A profile is a full Hermes home, so it needs more than config.yaml: without its own
# SOUL.md it inherits whatever `hermes profile create` copied from the default profile —
# i.e. the wrong identity — and without its own skills/ a task dispatched with
# `skills: [...]` fails with "Skill not found", because skills resolve under the
# PROFILE's home, not the root one.
for pdir in "${REPO_CONFIG_DIR}"/profiles/*/; do
  [ -f "${pdir}config.yaml" ] || continue
  pname="$(basename "${pdir}")"
  echo "==> Syncing profile: ${pname}"
  hermes profile create "${pname}" </dev/null >/dev/null 2>&1 || true
  PDIR="${HERMES_HOME}/profiles/${pname}"
  mkdir -p "${PDIR}"
  cp "${pdir}config.yaml" "${PDIR}/config.yaml"
  # A descrição é o que o orquestrador do kanban lê para rotear trabalho, e ela NÃO pode
  # depender do `create`: a partir do segundo boot o perfil já existe, o create sai em
  # erro e o `|| true` engole junto qualquer `--description`. `profile describe --text
  # --overwrite` é idempotente e reaplica o texto do repo a cada start, que é a mesma
  # regra do config e do SOUL: o disco é derivado do repo, sempre.
  if [ -f "${pdir}description.txt" ]; then
    hermes profile describe "${pname}" \
      --text "$(tr -d '\r' < "${pdir}description.txt")" --overwrite >/dev/null 2>&1 || true
  fi
  if [ -f "${pdir}SOUL.md" ]; then
    cp "${pdir}SOUL.md" "${PDIR}/SOUL.md"
  fi
  # Shared skills first, then the profile's own overrides on top.
  mkdir -p "${PDIR}/skills"
  if [ -d "${REPO_CONFIG_DIR}/skills" ]; then
    cp -R "${REPO_CONFIG_DIR}/skills/." "${PDIR}/skills/"
  fi
  if [ -d "${pdir}skills" ]; then
    cp -R "${pdir}skills/." "${PDIR}/skills/"
  fi
  touch "${PDIR}/.env"
  grep -vE "^TELEGRAM_" "${PDIR}/.env" > "${PDIR}/.env.tmp" 2>/dev/null || true
  grep -E "^TELEGRAM_" "${HERMES_HOME}/.env" >> "${PDIR}/.env.tmp" 2>/dev/null || true
  mv "${PDIR}/.env.tmp" "${PDIR}/.env"
done

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
