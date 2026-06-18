# Security Policy

## Reporting a vulnerability

Report privately via GitHub: **Security → Advisories → Report a vulnerability**.
Please do not open a public issue for security problems.

## Scope and posture

This repo runs an AI agent with shell/file/web tools on a personal machine. Key
boundaries:

- The agent executes inside the devcontainer (`terminal.backend: local`); the host
  filesystem is not mounted into it.
- Approvals are `manual`, secrets are redacted in output, and the Tirith command
  scanner runs **fail-closed**.
- Ollama and SearXNG bind `0.0.0.0` because the container reaches them via
  `host.docker.internal`; `scripts/firewall-host.sh` (and the LaunchDaemon
  installer) block them on the LAN. Grafana and Redis are loopback-only.
- The Telegram gateway answers only paired users (`TELEGRAM_ALLOWED_USERS`); it
  refuses to expose the bot when a token is set without an allowlist (the gateway
  itself still runs for the kanban dispatcher and cron). Unknown DMs are ignored.

## Secrets

Real secrets live only in gitignored files (`*.env`, `docker/searxng/settings.yml`);
only `*.example` templates are committed. If a
secret is ever committed, rotate it (new Telegram bot token, regenerate the
Redis/SearXNG secrets) and scrub history before publishing.

## Known residual risks

- The Hermes installer runs `curl … | bash` without a pinned checksum (no
  versioned URL is published upstream).
- pf firewall rules are not enabled by default at boot; the
  `install-firewall-daemon.sh` LaunchDaemon re-applies them.
