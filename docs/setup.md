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
  patches/            # idempotent post-install patches applied to Hermes (e.g. clickable /help)
config/               # synced to ~/.hermes/: config.yaml, SOUL.md (persona),
                      # ella_kb.yaml, gateway.json, skills/, .env.example
ingestion/            # ella_kb (RAG), ella_flow (workflow engine), ella_web (FastAPI)
web/                  # React Flow canvas: frontend/ + Dockerfile (served by `make web`)
qdrant/               # vector store for the knowledge base
tts/                  # local text-to-speech (voice replies)
miniflux/             # feed reader for the optional `feeds` connector
redis/
  docker-compose.yml  # shared, password-protected Redis on the hermes-shared network
searxng/
  docker-compose.yml  # web-search engine; cache/limiter on the shared Redis
  settings.yml.example
monitoring/
  docker-compose.yml  # Grafana + Loki + Promtail + Prometheus + blackbox + shippers
  grafana/ loki/ promtail/ prometheus/ blackbox/  # configs, dashboard, alert
scripts/              # HOST setup + lifecycle: Ollama, Redis, SearXNG, TTS, Qdrant,
                      # Miniflux, web, monitoring, launchd services, backup, firewall
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
./scripts/setup-tts-host.sh          # local voice replies on localhost:8880
./scripts/setup-qdrant-host.sh       # knowledge-base vector store on localhost:6333
./scripts/setup-monitoring-host.sh   # Grafana/Loki/Prometheus on localhost:3000
```

Run Redis before SearXNG (SearXNG uses it). The container reaches SearXNG at
`host.docker.internal:8888` (`SEARXNG_URL`), the TTS engine at
`host.docker.internal:8880`, and Qdrant at `host.docker.internal:6333`. First TTS
start downloads the voice model (a few minutes). `setup-qdrant-host.sh` prints an
API key — copy it into `~/.hermes/.env` as `QDRANT_API_KEY` so Ella can connect.
`make tts` / `make qdrant` run the same scripts.

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
| Voice in (STT) | local faster-whisper | installed by `postCreate.sh` |
| Voice out (TTS) | local Kokoro-FastAPI | `./scripts/setup-tts-host.sh` |
| Web search | local SearXNG | `./scripts/setup-searxng-host.sh` |
| Knowledge base | local Qdrant + `nomic-embed-text` | `./scripts/setup-qdrant-host.sh` |
| Feeds (optional) | local Miniflux | `./scripts/setup-miniflux-host.sh` |
| Telegram | gateway → `TELEGRAM_BOT_TOKEN` | see below |
| Identity / voice | `config/SOUL.md` | edit + rebuild |

### Knowledge base

Ella keeps a personal RAG memory: she captures links, files, and notes and recalls
them by meaning. It runs as an MCP server (`ella-kb`, registered in `config.yaml`)
backed by the local Qdrant; the `ella_kb` package is installed into the Hermes venv
by `postCreate.sh`. Source types are pluggable adapters — `files`, `urls`, and
`chat` ship enabled; `feeds` and `webhook` are wired but off by default. Toggle them
in `config/ella_kb.yaml` under `capabilities`. Each enabled type gets its own Qdrant
collection (`kb_<type>__nomic768`).

Copy the API key printed by `setup-qdrant-host.sh` into `~/.hermes/.env` as
`QDRANT_API_KEY`. Quick check from the container: `ella-kb init` then
`ella-kb capture --text "remember this" && ella-kb recall "this"`.

**Feeds (example connector).** Start Miniflux with `./scripts/setup-miniflux-host.sh`,
add the `MINIFLUX_*` lines it prints to `~/.hermes/.env`, subscribe to feeds in its
UI at `localhost:8930`, and set `feeds.enabled: true` in `config/ella_kb.yaml`
(optionally `include`/`exclude` keywords). `ella-kb poll feeds` ingests new relevant
items. For a proactive digest, create a cron job once:
`hermes cron create "every 1d at 08:30" "Send me my feeds digest" --skill feeds-digest --deliver telegram --name feeds-digest`.

**Webhook (example connector).** Set `KB_WEBHOOK_SECRET` in `~/.hermes/.env`, set
`webhook.enabled: true`, and run `ella-kb webhook-serve`. External services POST
`{"text": "...", "title": "...", "url": "..."}` to `/ingest` with an
`X-Signature: sha256=<hmac>` header.

### Web canvas

A browser/mobile UI to chat with Ella and build workflows visually — nodes are her
capabilities, wired on a canvas (solid edges = execution, dotted = the agent's
dependencies). Backend `ella-web` (FastAPI, installed into the Hermes venv); frontend
React + React Flow in `web/frontend`. Easiest: `make web` builds the frontend inside
Docker and serves the canvas at **http://localhost:8099** — no local Node/npm needed
(run the devcontainer once first so Ella's config is in the shared `hermes-data`
volume). For hot-reload dev with Node on the host, run `ella-web` plus
`cd web/frontend && npm run dev`. See [../web/README.md](../web/README.md).

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

**Clickable commands.** Commands are tappable two ways: the native command menu
(the `/` / menu button, populated via `set_my_commands`) and the `/help` listing.
Hermes wraps `/help` commands in backticks, which makes them monospace and stops
Telegram from auto-linking them; `patches/telegram-help-clickable.py` (applied by
`postCreate.sh`, idempotent, survives a Hermes reinstall) strips those backticks so
the listed commands stay tappable.

### Branding & avatar

`scripts/setup-telegram-branding.sh` (run in the container) sets Ella's bot name,
descriptions, and menu button via the Bot API. The command menu itself is managed
by Hermes.

The profile photo can only be set through **@BotFather → `/setuserpic`** (the Bot
API has no method for it). Generate an avatar — face-focused so it reads at small
size, warm and intelligent, not sexualized — and upload it there. A starting prompt
(mostly warmth, a touch of quiet competence):

> Head-and-shoulders portrait of a warm, intelligent young woman in her mid-twenties:
> long copper-red hair loosely braided in a few subtle strands, very expressive
> emerald-green eyes, fair skin, a soft discreet smile. She looks directly at the
> viewer with calm, quiet confidence — approachable and clearly intelligent. Warm
> amber light with a faint cool-blue rim; minimal holographic particles drifting
> softly around her, suggesting a living AI without overpowering the face. Sleek
> minimalist dark top. Cinematic realism, premium AI-assistant brand identity, clean
> background, centered composition, soft depth of field, highly detailed natural face
> and eyes. No weapons, armor, fantasy, robotic features, or sexualization. Reads well
> as a small circular avatar.

Negative prompt: `robot, android, helmet, armor, weapon, fantasy, anime, over-stylized, cleavage, sexualized, busy background, text, watermark, logo`.

## Monitoring

`./scripts/setup-monitoring-host.sh` brings up the stack; open
**http://localhost:3000** (loopback-only, no login) → dashboard *"Hermes — Live
Activity"*. It streams, live:

- **Agent / Telegram** activity from Hermes `agent.log` (via the `hermes-data` volume).
- **Ollama** requests and model loads from `~/.hermes-monitoring/ollama.log`.
- A **chat panel** with the real conversation text per Telegram user (name +
  masked id), shipped from Hermes' `state.db`.
- **Service status** (Ollama, SearXNG, Redis, voice, knowledge, Loki, Grafana,
  gateway) and live tool usage. An **Ollama-down alert** DMs Telegram; put the bot
  token + your chat id in `monitoring/.env` (gitignored).

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
