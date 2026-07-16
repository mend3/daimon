#!/usr/bin/env python3
"""Tiny Prometheus exporter for Hermes' own status. The agent/gateway run inside
his container (no HTTP endpoint), so blackbox can't probe them. This reads the
gateway lifecycle from agent.log (mounted read-only) and exposes whether the
Telegram gateway is currently connected. Stdlib only."""
import http.server
import os

LOG = os.environ.get("AGENT_LOG", "/hermes/logs/agent.log")
PORT = int(os.environ.get("PORT", "9101"))

UP = ("telegram connected", "Connected to Telegram", "Gateway running")
DOWN = ("Stopped gateway", "telegram disconnected", "Exiting with code", "Shutdown")


def gateway_up():
    try:
        sz = os.path.getsize(LOG)
        with open(LOG, "rb") as f:
            f.seek(max(0, sz - 262144))
            lines = f.read().decode(errors="ignore").splitlines()
    except Exception:
        return 0
    # Most recent lifecycle event wins.
    for line in reversed(lines):
        if any(s in line for s in DOWN):
            return 0
        if any(s in line for s in UP):
            return 1
    return 0


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            "# HELP hermes_gateway_up Telegram gateway/bot connected (1) or down (0)\n"
            "# TYPE hermes_gateway_up gauge\n"
            f'hermes_gateway_up{{service="gateway"}} {gateway_up()}\n'
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
