#!/usr/bin/env bash
# Set Daimon's Telegram bot branding (name, descriptions, menu button) via the Bot
# API. Run inside the devcontainer (reads ~/.hermes/.env) or with
# TELEGRAM_BOT_TOKEN exported.
#
# The bot's profile photo can only be set via @BotFather (/setuserpic) — the Bot
# API has no method for it. See docs/setup.md for the avatar prompt.
set -euo pipefail

TOKEN="${TELEGRAM_BOT_TOKEN:-}"
if [ -z "${TOKEN}" ] && [ -f "${HOME}/.hermes/.env" ]; then
  TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "${HOME}/.hermes/.env" | cut -d= -f2)"
fi
[ -n "${TOKEN}" ] || { echo "No TELEGRAM_BOT_TOKEN found (export it or run in the container)."; exit 1; }

API="https://api.telegram.org/bot${TOKEN}"
SHORT="Daimon — your private, local AI companion. I think with you, remember what matters, and help you get things done."
DESC="Hi, I'm Daimon — a private AI companion running on local, private infrastructure. I'm a thinking partner and an operator: I remember our work, search the web, read images and voice notes, and help you decide and execute — anticipating what comes next. Send me a message to begin."

curl -fsS "${API}/setMyName" --data-urlencode "name=Daimon" >/dev/null
curl -fsS "${API}/setMyShortDescription" --data-urlencode "short_description=${SHORT}" >/dev/null
curl -fsS "${API}/setMyDescription" --data-urlencode "description=${DESC}" >/dev/null
curl -fsS "${API}/setChatMenuButton" -H "Content-Type: application/json" \
  -d '{"menu_button":{"type":"commands"}}' >/dev/null

echo "Daimon's Telegram branding applied."
echo "Avatar: generate it (see docs/setup.md) and set it via @BotFather → /setuserpic."
