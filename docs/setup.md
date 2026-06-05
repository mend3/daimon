# Setup & operations

Detailed installation and infrastructure for running Hermes locally on macOS
(Apple Silicon) with Docker Desktop and Homebrew. For the overview, see the
[README](../README.md).

## Architecture

Hermes runs isolated in a **devcontainer**, driven by **gpt-oss:20b** served by
**Ollama** running natively on the macOS host so inference uses the Apple Silicon
GPU via Metal.

```
┌─────────────── macOS host ───────────────┐
│  Ollama (native, Metal GPU)               │
│    gpt-oss:20b → http://0.0.0.0:11434     │
│                       ▲                   │
│         host.docker.internal:11434        │
│                       │                   │
│  ┌──────────── devcontainer ───────────┐  │
│  │  Hermes Agent (CLI, isolated)        │ │
│  │    config: ~/.hermes/config.yaml     │ │
│  └──────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

Why this split: on a Mac, Ollama **inside** Docker is CPU-only (no Metal), which
makes inference painfully slow. Running Ollama natively keeps it fast while Hermes
stays sandboxed in the container.

Hermes requires a model with at least a **64K context window**. gpt-oss:20b serves
128K natively; the host script pins the runtime window to 64K to fit unified
memory. A model that maxes below 64K (e.g. `qwen3:8b` at 40K) is rejected at
startup.

## Repo layout

```
.devcontainer/
  devcontainer.json   # container def: volumes, host networking, env, lifecycle
  Dockerfile          # Debian base + git/curl/ripgrep/ffmpeg; runs container-boot.sh
  postCreate.sh       # installs Hermes (skipped once volumes are warm), syncs config
  container-boot.sh   # PID 1: starts the gateway, then keeps the container alive
  start-gateway.sh    # idempotent gateway launcher (no-op without a token)
config/
  config.yaml         # Hermes config → mounted to ~/.hermes/config.yaml
  SOUL.md             # agent identity/voice → mounted to ~/.hermes/SOUL.md
  .env.example        # secrets/env template
redis/
  docker-compose.yml  # shared, password-protected Redis on the hermes-shared network
searxng/
  docker-compose.yml  # web-search engine; cache/limiter on the shared Redis
  settings.yml.example
monitoring/
  docker-compose.yml  # Grafana + Loki + Promtail + Prometheus + blackbox + shippers
  grafana/ loki/ promtail/ prometheus/ blackbox/  # configs, dashboard, alert
scripts/              # HOST setup + lifecycle: Ollama, Redis, SearXNG, monitoring,
                      # launchd services, daily backup, LAN firewall
```

## Quick start

macOS host with Docker Desktop + Homebrew:

```bash
make up           # Ollama (Metal) + Redis + SearXNG + monitoring
# then open the folder in VS Code → "Reopen in Container" and run `hermes`
```

`make help` lists every target. The steps below explain each one.

### 1. On the macOS host — start Ollama and pull the model

```bash
./scripts/setup-ollama-host.sh          # defaults to gpt-oss:20b
# or pass another tag with a >=64K context window:
# ./scripts/setup-ollama-host.sh llama3.1:8b
```

This installs Ollama (via the official **`ollama-app` Homebrew cask** if needed),
binds it to `0.0.0.0:11434` so the container can reach it, and pulls the model.
Keep it running.

For image analysis, also pull the vision model used by the `vision` toolset:

```bash
ollama pull qwen2.5vl:7b
```

> The `ollama-app` cask provides Metal GPU acceleration on Apple Silicon. Confirm
> it is active with `grep -i metal /tmp/ollama.log` — expect `library=Metal`.

> Using the Ollama **menubar app** instead of the script? Make it listen on all
> interfaces once: `launchctl setenv OLLAMA_HOST 0.0.0.0:11434`, then quit and
> reopen the app.

### 2. Start the host services

```bash
./scripts/setup-redis-host.sh        # shared Redis (SearXNG's cache/limiter)
./scripts/setup-searxng-host.sh      # web search on localhost:8888
./scripts/setup-monitoring-host.sh   # Grafana/Loki/Prometheus on localhost:3000
```

Run Redis before SearXNG (SearXNG uses it). The container reaches SearXNG at
`host.docker.internal:8888` (`SEARXNG_URL`).

To make all of this (plus Ollama) start at login and survive reboots, install the
launchd agents instead:

```bash
./scripts/install-host-services.sh                 # managed Ollama + stacks + daily backup
sudo ./scripts/install-firewall-daemon.sh          # block Ollama/SearXNG on the LAN
```

### 3. Open the devcontainer

In VS Code (with the **Dev Containers** extension) or the `devcontainer` CLI:

- **VS Code:** open this folder → "Reopen in Container".
- **CLI:** `devcontainer up --workspace-folder .`

On first create, `postCreate.sh` installs Hermes, copies `config/config.yaml` and
`config/SOUL.md` into `~/.hermes/`, and verifies Ollama is reachable.

### 4. Run

Inside the container:

```bash
hermes            # start chatting against the local model
hermes config     # view the active configuration
hermes doctor     # diagnostics
```

## Integrations

| Capability | Backend | Setup |
|------------|---------|-------|
| Chat / tools | `gpt-oss:20b` on host Ollama | default |
| Vision | `qwen2.5vl:7b` on host Ollama | `ollama pull qwen2.5vl:7b` |
| Voice (STT) | local faster-whisper | installed by `postCreate.sh` |
| Web search | local SearXNG | `./scripts/setup-searxng-host.sh` |
| Telegram | gateway → `TELEGRAM_BOT_TOKEN` | see below |
| Identity / voice | `config/SOUL.md` | edit + rebuild |

### Telegram

Create a bot with [@BotFather](https://t.me/BotFather), then inside the container:

```bash
hermes gateway setup          # paste the token, pair your account
```

Once the token is in `~/.hermes/.env`, the gateway **auto-starts with the
container**: the container's command (`.devcontainer/container-boot.sh`) launches
it under PID 1 on every start, so it needs no open terminal. Start it manually with:

```bash
bash .devcontainer/start-gateway.sh    # detached; or: hermes gateway run (foreground)
```

The bot answers only paired users (`TELEGRAM_ALLOWED_USERS`). Manage access with
`hermes pairing approve|revoke|list` or by editing `TELEGRAM_ALLOWED_USERS`. The
token lives in `~/.hermes/.env`, never in the repo.

## Monitoring

`./scripts/setup-monitoring-host.sh` brings up the stack; open
**http://localhost:3000** (loopback-only, no login) → dashboard *"Hermes — Live
Activity"*. It streams, live:

- **Agent / Telegram** activity from Hermes `agent.log` (via the `hermes-data` volume).
- **Ollama** requests and model loads from `~/.hermes-monitoring/ollama.log`.
- A **chat panel** with the real conversation text per Telegram user (name +
  masked id), shipped from Hermes' `state.db`.
- **Service status** (Ollama, SearXNG, Redis, Loki, Grafana, gateway) and live tool
  usage. An **Ollama-down alert** DMs Telegram; put the bot token + your chat id in
  `monitoring/.env` (gitignored).

Stop with `docker compose -f monitoring/docker-compose.yml down`.

## Changing the model

1. Pull a tag with a ≥64K context window on the host: `ollama pull llama3.1:8b`
2. Edit `config/config.yaml` → `model.default` (and the `providers.custom.models`
   timeout key) to match.
3. Rebuild the container (or `cp config/config.yaml ~/.hermes/config.yaml` inside it).

## What persists

Two named Docker volumes survive rebuilds, so a rebuild is fast and skips the
Hermes install:

- **`hermes-data`** → `~/.hermes/` (config, `memories/`, `sessions/`, `skills/`,
  `logs/`, `state.db`, agent code).
- **`hermes-local`** → `~/.local/` (uv-managed Python runtime and the `hermes`
  launcher the venv links to).

Delete both with `docker volume rm hermes-data hermes-local` for a clean slate
(the next start reinstalls Hermes).

## Notes

- **Secrets:** real secrets go in `~/.hermes/.env` inside the container (seeded
  from `config/.env.example`). `config/.env` is git-ignored.
- **Web search** runs against the local SearXNG (`web.backend: searxng`,
  `SEARXNG_URL=http://host.docker.internal:8888`). Swap in a hosted backend by
  setting its key in `.env` and `web.backend` in `config.yaml`.
- **No host filesystem access:** the agent's terminal backend is `local`, scoped
  to the container only.
- **Network:** Ollama and SearXNG bind `0.0.0.0` (the container reaches them via
  `host.docker.internal`); `scripts/firewall-host.sh` blocks them on the LAN.
  Grafana and Redis are loopback-only.
- **Backups:** the `com.hermes.backup` launchd agent runs `scripts/backup-hermes.sh`
  daily, archiving the `hermes-data` volume to `~/hermes-backups`.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and [SECURITY.md](../SECURITY.md) for
conventions and the security posture.
