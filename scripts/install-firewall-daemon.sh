#!/usr/bin/env bash
# Run on the macOS HOST with sudo. Installs a LaunchDaemon that re-applies the
# Hermes pf firewall (scripts/firewall-host.sh enable) at every boot, so the LAN
# block on Ollama/SearXNG survives reboots. pf is loaded but not enabled by
# default at boot, so without this the rules go inert after a restart.
#
#   sudo ./scripts/install-firewall-daemon.sh            # install + start
#   sudo ./scripts/install-firewall-daemon.sh uninstall  # remove
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.hermes.firewall"
PLIST="/Library/LaunchDaemons/${LABEL}.plist"
FW="${REPO}/scripts/firewall-host.sh"

if [ "${1:-install}" = "uninstall" ]; then
  launchctl bootout "system/${LABEL}" 2>/dev/null || true
  rm -f "${PLIST}"
  "${FW}" disable || true
  echo "Removed ${LABEL} and disabled the firewall."
  exit 0
fi

[ -x "${FW}" ] || { echo "Not found/executable: ${FW}"; exit 1; }

cat > "${PLIST}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${FW}</string>
    <string>enable</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/var/log/hermes-firewall.log</string>
  <key>StandardErrorPath</key><string>/var/log/hermes-firewall.log</string>
</dict></plist>
PLIST

# LaunchDaemons must be owned by root:wheel and not writable by group/others.
chown root:wheel "${PLIST}"
chmod 644 "${PLIST}"

launchctl bootout "system/${LABEL}" 2>/dev/null || true
launchctl bootstrap system "${PLIST}"
launchctl enable "system/${LABEL}"
launchctl kickstart -k "system/${LABEL}"

echo "Installed ${LABEL} (runs at every boot)."
echo "Verify now:  sudo ./scripts/firewall-host.sh status"
echo "Boot log:    /var/log/hermes-firewall.log"
