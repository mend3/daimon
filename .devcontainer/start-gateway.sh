#!/usr/bin/env bash
# postStartCommand hook: bring the Hermes messaging gateway up with the container.
# No-op when it is already running or no Telegram token is configured. Always
# exits 0 so a gateway problem never blocks container start.
set -u

mkdir -p ~/.hermes/logs

# Already running — nothing to do.
if pgrep -f "gateway run" >/dev/null 2>&1; then
  exit 0
fi

# Nothing to serve without a token.
if ! grep -qE "^TELEGRAM_BOT_TOKEN=.+" ~/.hermes/.env 2>/dev/null; then
  exit 0
fi

export HERMES_ACCEPT_HOOKS=1
setsid bash -c 'exec hermes gateway run' >~/.hermes/logs/gateway.out 2>&1 </dev/null &

exit 0
