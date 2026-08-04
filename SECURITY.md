# Security Policy

## Reporting a vulnerability

Report privately via GitHub: **Security → Advisories → Report a vulnerability**.
Please do not open a public issue for security problems.

## Scope and posture

This repo runs an AI agent with shell/file/web tools on a personal machine. Key
boundaries:

- The agent executes inside his own container (`terminal.backend: local`); of the host
  filesystem, only this repo is mounted into it.
- Approvals are `manual`, secrets are redacted in output, and the Tirith command
  scanner runs **fail-closed**.
- Daimon and his sidecars share an external Docker network with your infra stack, and
  that network is the isolation boundary — anything else attached to it can reach them. SearXNG and TTS live in the shared stack now, bound to loopback there; on macOS
- The Telegram gateway answers only paired users (`TELEGRAM_ALLOWED_USERS`); it
  refuses to expose the bot when a token is set without an allowlist (the gateway
  itself still runs for the kanban dispatcher and cron). Unknown DMs are ignored.

## Secrets

Real secrets live only in gitignored files (`*.env`);
only `*.example` templates are committed. If a
secret is ever committed, rotate it (new Telegram bot token, regenerate the
Redis secrets) and scrub history before publishing.

## Known residual risks

- The Hermes installer runs `curl … | bash` without a pinned checksum (no
  versioned URL is published upstream).
- pf firewall rules are not enabled by default at boot; the
  (SearXNG no longer publishes from here — it binds to loopback in the shared stack.)
