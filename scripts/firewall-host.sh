#!/usr/bin/env bash
# Run on the macOS HOST with sudo. Ollama (11434) and SearXNG (8888) must bind
# 0.0.0.0 so the devcontainer can reach them via host.docker.internal, which
# exposes them on the LAN. This blocks inbound to those ports on the *external*
# network interface only — the container path goes through Docker's internal
# vmnet, not the external interface, so it keeps working. Grafana (3000) is
# already loopback-only.
#
#   sudo ./scripts/firewall-host.sh enable
#   sudo ./scripts/firewall-host.sh disable
#
# Note: pf rules do not persist across reboot on their own; re-run `enable`
# after a reboot, or wire it into a LaunchDaemon if you want it permanent.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }

ANCHOR=/etc/pf.anchors/com.hermes.lockdown
PORTS="{ 11434, 8888 }"
IFACE="$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')"

case "${1:-enable}" in
  enable)
    [ -n "${IFACE}" ] || { echo "Could not detect the default interface."; exit 1; }
    printf 'block in on %s proto tcp from any to any port %s\n' "${IFACE}" "${PORTS}" > "${ANCHOR}"
    pfctl -a com.hermes.lockdown -f "${ANCHOR}"
    pfctl -E 2>/dev/null || true
    echo "Enabled: inbound to ${PORTS} blocked on ${IFACE} (LAN). Loopback and the"
    echo "container's host.docker.internal path are unaffected."
    ;;
  disable)
    pfctl -a com.hermes.lockdown -F all 2>/dev/null || true
    rm -f "${ANCHOR}"
    echo "Disabled: Hermes firewall rules removed."
    ;;
  *)
    echo "usage: sudo $0 [enable|disable]"; exit 1
    ;;
esac
