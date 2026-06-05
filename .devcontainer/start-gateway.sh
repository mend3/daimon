#!/usr/bin/env bash
# Bring the Hermes messaging gateway up. Called by container-boot.sh (PID 1) on
# every container start. No-op when already running or no Telegram token is set.
# Always exits 0 so a gateway problem never blocks container start.
set -u

ENV_FILE=~/.hermes/.env
mkdir -p ~/.hermes/logs

# Already running — nothing to do.
if pgrep -f "gateway run" >/dev/null 2>&1; then
  exit 0
fi

# Nothing to serve without a token.
if ! grep -qE "^TELEGRAM_BOT_TOKEN=.+" "${ENV_FILE}" 2>/dev/null; then
  exit 0
fi

# Refuse to expose an agent with shell/file tools to an open bot: require an
# allowlist (or an explicit opt-in to open access) before starting.
if ! grep -qE "^TELEGRAM_ALLOWED_USERS=.+" "${ENV_FILE}" 2>/dev/null \
   && ! grep -qiE "^(GATEWAY_ALLOW_ALL_USERS|TELEGRAM_ALLOW_ALL_USERS)=true" "${ENV_FILE}" 2>/dev/null; then
  echo "[start-gateway] REFUSING to start: TELEGRAM_BOT_TOKEN is set but no" \
       "TELEGRAM_ALLOWED_USERS allowlist. Pair your account (hermes gateway setup)" \
       "or set TELEGRAM_ALLOW_ALL_USERS=true to opt into open access." \
       >> ~/.hermes/logs/gateway.out
  exit 0
fi

export HERMES_ACCEPT_HOOKS=1
# --replace clears a stale PID lock (e.g. left by a crashed run or a `gateway
# restart`) so a fresh container start always gets a clean single instance.
setsid bash -c 'exec hermes gateway run --replace' >~/.hermes/logs/gateway.out 2>&1 </dev/null &

exit 0
