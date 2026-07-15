# Setup & operations

Detailed installation and infrastructure for running Daimon next to a shared infra
stack. For the overview, see the [README](../README.md).

## Architecture

Hermes runs isolated in a **devcontainer**, driven by **OpenAI gpt-5-mini** by default
with **gpt-oss:20b** on Ollama as the local profile and automatic fallback (Ollama also
serves vision + embeddings).

Everything shared is **external**: you run Ollama, Redis, Qdrant and the observability
plane on a Docker network Daimon joins — `SHARED_NETWORK`, default `shared` — and Daimon
reaches them **by DNS**. Daimon declares none of them; it adds only its own sidecars.

```
┌──────────── shared network (SHARED_NETWORK) ─────────────┐
│                                                           │
│  your infra stack        Daimon's sidecars                │
│    ollama:11434            daimon-searxng:8080            │
│    qdrant:6333             daimon-tts:8880                │
│    redis:6379 (db 5)                                      │
│    loki:3100 · grafana:3000                               │
│                       ▲                                   │
│  ┌──────────── devcontainer ─────────────┐                │
│  │  Hermes Agent (CLI, isolated)          │               │
│  │    config: ~/.hermes/config.yaml       │               │
│  └────────────────────────────────────────┘               │
└───────────────────────────────────────────────────────────┘
```

Why this split: the shared services are shared. Running a second Ollama beside the one
your stack already serves wastes the VRAM it is holding and splits the model cache in
two. Daimon consumes; the stack provides.

Hermes requires a model with at least a **64K context window** — a model that maxes
below it (e.g. `qwen3:8b` at 40K) is rejected at startup. The window is served by *your*
Ollama (`OLLAMA_CONTEXT_LENGTH`) for all of its consumers at once, so it is your call,
not Daimon's; `make doctor` reports the models it needs rather than pulling them.

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
                      # daimon_kb.yaml, gateway.json, skills/, .env.example
ingestion/            # daimon_kb (RAG), daimon_flow (headless workflow engine)
docker-compose.yml    # Daimon's sidecars (searxng, tts, telemetry) with profiles
docker/               # container configs for the sidecars:
  searxng/settings.yml.example  # web-search engine; cache/limiter on the shared Redis
  chat-shipper/ status-exporter/  # app-level telemetry sidecars (see Monitoring)
scripts/              # setup + lifecycle: SearXNG, TTS, backup, doctor
                      # (launchd/firewall ones are macOS-only)

Ollama, Redis, Qdrant, Miniflux and the observability plane (Grafana/Loki/Prometheus)
are **not** run by Daimon — your shared infra stack serves them on the external network.
Start it first. Daimon reaches them by DNS: Ollama at `ollama:11434`, Redis at
`redis:6379` (logical db index 5), Qdrant at `qdrant:6333`, Loki at `loki:3100`.
```

## Quick start

```bash
export SHARED_NETWORK=shared   # the network your infra stack runs on
make doctor                    # what's reachable, what's missing
make up                        # Daimon's sidecars: SearXNG + TTS
# then open the folder in VS Code → "Reopen in Container" and run `hermes`
```

Start your **shared infra stack first** — it owns the network and the
Ollama/Redis/Qdrant/observability plane Daimon consumes. `make help` lists every target.
The steps below explain each one.

### 1. On your shared stack — the models Daimon needs

Daimon pulls nothing: the models live on your Ollama, served at a **≥64K** window
(`OLLAMA_CONTEXT_LENGTH`).

| Model | Used for | Missing means |
|---|---|---|
| `gpt-oss:20b` | local profile + automatic fallback | no local fallback; `ollama` profile unusable |
| `qwen2.5vl:7b` | the `vision` toolset | vision degraded |
| `nomic-embed-text` | knowledge-base embeddings (768-dim) | knowledge base degraded |

`make doctor` reports which are present. The OpenAI default profile answers without any
of them.

### 2. Start Daimon's sidecars

```bash
make settings                        # generate docker/searxng/settings.yml (once)
./scripts/setup-searxng-host.sh      # web search on localhost:8888
./scripts/setup-tts-host.sh          # local voice replies on localhost:8880
```

SearXNG's cache/limiter uses the shared Redis (`redis:6379`, logical db index 5). The
container reaches SearXNG at `daimon-searxng:8080` (`SEARXNG_URL`) and the TTS engine at
`daimon-tts:8880`; both also publish on the host (`localhost:8888` / `localhost:8880`).
First TTS start downloads the voice model (a few minutes). `make searxng` / `make tts`
run the same scripts. The knowledge base points at the shared Qdrant (`qdrant:6333`) via
`config/daimon_kb.yaml` — no Qdrant setup of your own.

On a macOS host, launchd agents can start the sidecars at login and survive reboots:

```bash
./scripts/install-host-services.sh                 # stacks + daily backup
sudo ./scripts/install-firewall-daemon.sh          # block SearXNG on the LAN
```

### 3. Open the devcontainer

In VS Code (with the **Dev Containers** extension) or the `devcontainer` CLI:

- **VS Code:** open this folder → "Reopen in Container".
- **CLI:** `devcontainer up --workspace-folder .`

The container joins the shared network (`SHARED_NETWORK` from your environment), so
start your stack first. On first create, `postCreate.sh` installs Hermes, copies
`config/config.yaml` and `config/SOUL.md` into `~/.hermes/`, and verifies Ollama is
reachable.

### 4. Run

Inside the container:

```bash
hermes            # start chatting (default: OpenAI gpt-5-mini, local fallback)
hermes config     # view the active configuration
hermes doctor     # diagnostics
```

## Integrations

| Capability | Backend | Setup |
|------------|---------|-------|
| Chat / tools | OpenAI `gpt-5-mini` (`openai-api`) | default; `gpt-oss:20b` on Ollama = `ollama` profile + fallback |
| Vision | `qwen2.5vl:7b` on the shared Ollama | pulled on your stack |
| Voice in (STT) | local faster-whisper | installed by `postCreate.sh` |
| Voice out (TTS) | local Kokoro-FastAPI | `./scripts/setup-tts-host.sh` |
| Web search | local SearXNG | `./scripts/setup-searxng-host.sh` |
| Knowledge base | the shared Qdrant (`qdrant:6333`) + `nomic-embed-text` | provided by your shared stack |
| Feeds (optional) | a Miniflux of your own | `MINIFLUX_*` in `~/.hermes/.env` |
| Telegram | gateway → `TELEGRAM_BOT_TOKEN` | see below |
| Identity / voice | `config/SOUL.md` | edit + rebuild |

### Knowledge base

Daimon keeps a personal RAG memory: she captures links, files, and notes and recalls
them by meaning. It runs as an MCP server (`daimon-kb`, registered in `config.yaml`)
backed by the shared Qdrant (`qdrant:6333`); the `daimon_kb`
package is installed into the Hermes venv by `postCreate.sh`. Source types are
pluggable adapters — `files`, `urls`, and `chat` ship enabled; `feeds` and `webhook`
are wired but off by default. Toggle them in `config/daimon_kb.yaml` under
`capabilities`. Each enabled type gets its own Qdrant collection
(`kb_<type>__nomic768`).

Qdrant is provided by your shared stack — point `config/daimon_kb.yaml` at `qdrant:6333` and set
any required `QDRANT_API_KEY` in `~/.hermes/.env` to match the shared config. Quick
check from the container: `daimon-kb init` then
`daimon-kb capture --text "remember this" && daimon-kb recall "this"`.

**Feeds (example connector).** Miniflux is not part of Daimon — run your own.
Add the `MINIFLUX_*` lines to `~/.hermes/.env` pointing at it, subscribe to feeds in its
UI, and set
`feeds.enabled: true` in `config/daimon_kb.yaml`
(optionally `include`/`exclude` keywords). `daimon-kb poll feeds` ingests new relevant
items. For a proactive digest, create a cron job once:
`hermes cron create "every 1d at 08:30" "Send me my feeds digest" --skill feeds-digest --deliver telegram --name feeds-digest`.

**Webhook (example connector).** Set `KB_WEBHOOK_SECRET` in `~/.hermes/.env`, set
`webhook.enabled: true`, and run `daimon-kb webhook-serve`. External services POST
`{"text": "...", "title": "...", "url": "..."}` to `/ingest` with an
`X-Signature: sha256=<hmac>` header.

### Workflows

Daimon's workflow engine (`daimon_flow`) is headless: workflows are node graphs —
triggers, the agent, tools, logic, and outputs — defined in config/code and run with
live state, no UI. Nodes are Daimon's own capabilities; new node types drop into
`ingestion/daimon_flow/nodes/` (or ship out-of-tree via a `daimon_flow.nodes` entry
point).

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

`scripts/setup-telegram-branding.sh` (run in the container) sets Daimon's bot name,
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

The observability plane (Grafana/Loki/Prometheus/Promtail/blackbox) lives on your
shared infra stack — Daimon does not run its own. The
dashboards, alert rules, and scrape configs of record live with that stack, and you
open Grafana from there.

Daimon keeps two app-level telemetry **sidecars** (`docker-compose.yml`, `monitoring`
profile, started by `make monitoring` or the login agent), both on the shared network:

- **chat-shipper** — pushes real conversation text per Telegram user (name + masked
  id) from Hermes' `state.db` to the shared Loki (`loki:3100`) for the Grafana chat panel.
- **status-exporter** — exposes `hermes_gateway_up` (read from `agent.log`) at
  `daimon-status-exporter:9101/metrics`, scraped by the shared Prometheus, since the
  agent runs inside the devcontainer where blackbox can't probe it.

Stop the sidecars with `docker compose --profile monitoring down`.

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
- **Web search** runs against Daimon's SearXNG sidecar (`web.backend: searxng`,
  `SEARXNG_URL=http://daimon-searxng:8080`). Swap in a hosted backend by
  setting its key in `.env` and `web.backend` in `config.yaml`.
- **No host filesystem access:** the agent's terminal backend is `local`, scoped
  to the container only.
- **Network:** everything Daimon talks to is reached by DNS on the shared network,
  which the devcontainer joins. That network is the isolation boundary: anything else on
  it can reach Daimon's sidecars. SearXNG and TTS also publish on the host
  (`localhost:8888` / `localhost:8880`) for convenience; on macOS
  `scripts/firewall-host.sh` blocks SearXNG on the LAN.
- **Backups:** the `com.hermes.backup` launchd agent runs `scripts/backup-hermes.sh`
  daily, archiving the `hermes-data` volume to `~/hermes-backups`. Qdrant is a
  rebuildable index provided by your shared stack, so it is backed up there, not by Daimon.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and [SECURITY.md](../SECURITY.md) for
conventions and the security posture.
