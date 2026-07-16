#!/usr/bin/env bash
# Run on the macOS HOST with sudo. Ollama (11434) and SearXNG (8888) must bind
# 0.0.0.0 so Daimon's container can reach them via host.docker.internal, which
# exposes them on the LAN. This blocks inbound to those ports on the physical
# (en*) interfaces only — the container path goes through Docker's internal
# vmnet, not en*, so it keeps working. Grafana (3000) is already loopback-only.
#
#   sudo ./scripts/firewall-host.sh enable
#   sudo ./scripts/firewall-host.sh disable
#   sudo ./scripts/firewall-host.sh status
#
# A pf anchor only takes effect when the main ruleset references it, so `enable`
# also adds an `anchor`/`load anchor` block to /etc/pf.conf (marked, reversible)
# and reloads pf. /etc/pf.conf is backed up to /etc/pf.conf.hermes-bak first.
# Note: re-run `enable` after a reboot (or wire a LaunchDaemon) for persistence.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }

ANCHOR_NAME="com.hermes.lockdown"
ANCHOR_FILE="/etc/pf.anchors/${ANCHOR_NAME}"
PF_CONF="/etc/pf.conf"
BEGIN="# >>> hermes-lockdown >>>"
END="# <<< hermes-lockdown <<<"
PORTS="{ 11434, 8888 }"

remove_markers() { # strip our block from pf.conf if present
  if grep -qF "${BEGIN}" "${PF_CONF}"; then
    sed -i '' "/${BEGIN}/,/${END}/d" "${PF_CONF}"
  fi
}

case "${1:-enable}" in
  enable)
    # All physical interfaces (WiFi + Ethernet), e.g. en0 en1.
    IFACES="$(ifconfig -l | tr ' ' '\n' | grep -E '^en[0-9]+$' | tr '\n' ' ')"
    [ -n "${IFACES}" ] || { echo "No en* interfaces found."; exit 1; }
    IFLIST="{ $(echo "${IFACES}" | sed 's/ *$//' | sed 's/ /, /g') }"

    printf 'block drop in quick on %s proto tcp from any to any port %s\n' \
      "${IFLIST}" "${PORTS}" > "${ANCHOR_FILE}"

    [ -f "${PF_CONF}.hermes-bak" ] || cp "${PF_CONF}" "${PF_CONF}.hermes-bak"
    remove_markers
    {
      echo "${BEGIN}"
      echo "anchor \"${ANCHOR_NAME}\""
      echo "load anchor \"${ANCHOR_NAME}\" from \"${ANCHOR_FILE}\""
      echo "${END}"
    } >> "${PF_CONF}"

    pfctl -ef "${PF_CONF}" 2>&1 | grep -vE "ALTQ|^$" || true
    echo "---"
    echo "Active rules in anchor ${ANCHOR_NAME}:"
    pfctl -a "${ANCHOR_NAME}" -sr 2>/dev/null || echo "  (none — anchor not loaded!)"
    echo "Blocking inbound ${PORTS} on: ${IFACES}"
    ;;

  disable)
    pfctl -a "${ANCHOR_NAME}" -F all 2>/dev/null || true
    rm -f "${ANCHOR_FILE}"
    remove_markers
    pfctl -f "${PF_CONF}" 2>&1 | grep -vE "ALTQ|^$" || true
    echo "Hermes firewall rules removed; pf reloaded from ${PF_CONF}."
    ;;

  status)
    echo "pf enabled: $(pfctl -s info 2>/dev/null | awk '/Status:/{print $2}')"
    echo "anchor ${ANCHOR_NAME} rules:"
    pfctl -a "${ANCHOR_NAME}" -sr 2>/dev/null || echo "  (none)"
    ;;

  *)
    echo "usage: sudo $0 [enable|disable|status]"; exit 1
    ;;
esac
