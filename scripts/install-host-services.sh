#!/usr/bin/env bash
# Install per-user LaunchAgents so the host side survives reboot/logout:
#   com.hermes.ollama  — Ollama as a managed service (RunAtLoad + KeepAlive)
#   com.hermes.stacks  — bring up SearXNG + monitoring at login
#   com.hermes.backup  — daily backup of the hermes-data and Qdrant volumes
# Idempotent; re-run to update. No sudo required (user agents).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LA="${HOME}/Library/LaunchAgents"
U="$(id -u)"
OLLAMA_BIN="$(command -v ollama || echo /opt/homebrew/bin/ollama)"
mkdir -p "${LA}" "${HOME}/.hermes-monitoring"

reload() { # <label> <plist>
  launchctl bootout "gui/${U}/$1" 2>/dev/null || true
  launchctl bootstrap "gui/${U}" "$2"
  launchctl enable "gui/${U}/$1" 2>/dev/null || true
}

echo "==> com.hermes.ollama (managed Ollama service)"
# Free the port from any manual `ollama serve` so launchd owns it.
pkill -f "ollama serve" 2>/dev/null || true
sleep 2
cat > "${LA}/com.hermes.ollama.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.hermes.ollama</string>
  <key>ProgramArguments</key><array><string>${OLLAMA_BIN}</string><string>serve</string></array>
  <key>EnvironmentVariables</key><dict>
    <key>OLLAMA_HOST</key><string>0.0.0.0:11434</string>
    <key>OLLAMA_CONTEXT_LENGTH</key><string>65536</string>
    <key>OLLAMA_FLASH_ATTENTION</key><string>1</string>
    <key>OLLAMA_KV_CACHE_TYPE</key><string>q8_0</string>
    <key>OLLAMA_NUM_PARALLEL</key><string>1</string>
    <key>OLLAMA_MAX_LOADED_MODELS</key><string>1</string>
    <key>OLLAMA_KEEP_ALIVE</key><string>-1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${HOME}/.hermes-monitoring/ollama.log</string>
  <key>StandardErrorPath</key><string>${HOME}/.hermes-monitoring/ollama.log</string>
</dict></plist>
PLIST
reload com.hermes.ollama "${LA}/com.hermes.ollama.plist"

echo "==> com.hermes.stacks (SearXNG + monitoring at login)"
cat > "${LA}/com.hermes.stacks.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.hermes.stacks</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>${REPO}/scripts/start-host-services.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>${HOME}/.hermes-monitoring/stacks.log</string>
  <key>StandardErrorPath</key><string>${HOME}/.hermes-monitoring/stacks.log</string>
</dict></plist>
PLIST
reload com.hermes.stacks "${LA}/com.hermes.stacks.plist"

echo "==> com.hermes.backup (daily 03:30)"
cat > "${LA}/com.hermes.backup.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.hermes.backup</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>-c</string><string>${REPO}/scripts/backup-hermes.sh; ${REPO}/scripts/backup-qdrant-host.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>${HOME}/.hermes-monitoring/backup.log</string>
  <key>StandardErrorPath</key><string>${HOME}/.hermes-monitoring/backup.log</string>
</dict></plist>
PLIST
reload com.hermes.backup "${LA}/com.hermes.backup.plist"

echo "==> Done. Verify: launchctl print gui/${U}/com.hermes.ollama | grep state"
