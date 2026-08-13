# Setup & operations

Detailed installation and infrastructure for running Daimon next to a shared infra
stack. For the overview, see the [README](../README.md).

## Architecture

Hermes runs isolated in **its own container**, brought up by compose alongside his
sidecars (`make up`). He is driven by the local **gpt-oss:20b** on Ollama, which also
serves vision.

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
│  ┌────────── agent container ────────────┐               │
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
Ollama (`OLLAMA_CONTEXT_LENGTH`, or a `num_ctx` baked into the model) for all of its
consumers at once, so it is your call, not Daimon's; `make doctor` reports the models it
needs rather than pulling them. Keep `model.context_length` in `config/config.yaml` equal
to what is actually served: claim more and Hermes budgets a window the server quietly
truncates, which reads as replies cut short mid-sentence, not as an error.

## Repo layout

```
docker-compose.yml    # Daimon + his sidecars (searxng, tts, telemetry), by profile
docker/agent/         # the container Hermes runs in:
  Dockerfile          # Debian base + git/curl/ripgrep/ffmpeg/node; runs entrypoint.sh
  entrypoint.sh       # PID 1: setup, then the gateway, then keeps the container alive
  setup.sh            # installs Hermes (skipped once volumes are warm), syncs config
  start-gateway.sh    # idempotent gateway launcher (no-op without a token)
  patches/            # idempotent post-install patches applied to Hermes (e.g. clickable /help)
.devcontainer/        # optional dev shell for editing this repo — same image, same
                      # setup.sh, no gateway (see "Editing this repo")
config/               # synced to ~/.hermes/: config.yaml, SOUL.md (persona),
                      # gateway.json, skills/, .env.example
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
make up                        # Daimon + his sidecars (SearXNG, TTS)
docker compose exec agent hermes   # talk to him
```

Start your **shared infra stack first** — it owns the network and the
Ollama/Redis/Qdrant/observability plane Daimon consumes. `make help` lists every target.
The steps below explain each one.

### 1. On your shared stack — the models Daimon needs

Daimon pulls nothing: the models live on your Ollama, served at a **≥64K** window
(`OLLAMA_CONTEXT_LENGTH`).

| Model | Used for | Missing means |
|---|---|---|
| `gpt-oss:20b` | the default model (and the `ollama` profile) | Daimon can't answer |
| `qwen2.5vl:7b` | the `vision` toolset | vision degraded |

`make doctor` reports which are present. There is no fallback provider, so a missing
model degrades the capability that needs it.

### 2. Start Daimon's sidecars

```bash
# Search and voice come from the shared stack (the oracle), not from here:
#   oracle$ make up searxng            # web search on searxng:8080 (127.0.0.1:8888)
#   oracle$ make up nvidia speech      # voice on tts:8880 (127.0.0.1:8880)
```

SearXNG's cache/limiter uses the shared Redis (`redis:6379`, logical db index 5). The
container reaches SearXNG at `daimon-searxng:8080` (`SEARXNG_URL`) and the TTS engine at
`daimon-tts:8880`; both also publish on the host (`localhost:8888` / `localhost:8880`).
First TTS start downloads the voice model (a few minutes). Those services
run the same scripts.

On a macOS host, launchd agents can start the sidecars at login and survive reboots:

```bash
./scripts/install-host-services.sh                 # stacks + daily backup
```

### 3. Start Daimon

```bash
make agent        # build + start the container Hermes runs in (part of `make up`)
```

It joins the shared network (`SHARED_NETWORK` from your environment), so start your
stack first. On every start `setup.sh` installs Hermes if the volumes are cold, copies
`config/config.yaml` and `config/SOUL.md` into `~/.hermes/`, and verifies Ollama is
reachable — then the gateway starts, so Telegram works with no terminal open.
`docker compose logs -f agent` shows all of it.

### 4. Run

```bash
docker compose exec agent hermes          # start chatting (default: local gpt-oss:20b)
docker compose exec agent hermes config   # view the active configuration
docker compose exec agent hermes doctor   # diagnostics
```

### Editing this repo

`.devcontainer/` is a dev shell for working on Daimon from any machine, whatever the
host OS: same image, same `setup.sh`, so what you edit against is what compose runs.
Open the folder in a Dev Containers client, or `make devcontainer`. It starts no
gateway — it shares the `hermes-data` volume with the running container, and two
gateways on one `state.db` is one too many.

## Integrations

| Capability | Backend | Setup |
|------------|---------|-------|
| Chat / tools | `gpt-oss:20b` on the shared Ollama | default; no fallback provider |
| Vision | `qwen2.5vl:7b` on the shared Ollama | pulled on your stack |
| Voice in (STT) | local faster-whisper | installed by `setup.sh` |
| Voice out (TTS) | Kokoro-FastAPI in the shared stack | oracle: `make up nvidia speech` |
| Web search | SearXNG in the shared stack | oracle: `make up searxng` |
| Telegram | gateway → `TELEGRAM_BOT_TOKEN` | see below |
| Identity / voice | `config/SOUL.md` | edit + `docker compose restart agent` |

### Telegram

Create a bot with [@BotFather](https://t.me/BotFather), then inside the container:

```bash
docker compose exec agent hermes gateway setup   # paste the token, pair your account
```

Once the token is in `~/.hermes/.env`, the gateway **auto-starts with the container**:
the entrypoint (`docker/agent/entrypoint.sh`) launches it as a child of PID 1 on every
start, so it needs no open terminal. Start it manually with:

```bash
docker compose exec agent bash docker/agent/start-gateway.sh   # detached
# or, in the foreground: docker compose exec agent hermes gateway run
```

The bot answers only paired users (`TELEGRAM_ALLOWED_USERS`). Manage access with
`hermes pairing approve|revoke|list` or by editing `TELEGRAM_ALLOWED_USERS`. The
token lives in `~/.hermes/.env`, never in the repo.

**Clickable commands.** Commands are tappable two ways: the native command menu
(the `/` / menu button, populated via `set_my_commands`) and the `/help` listing.
Hermes wraps `/help` commands in backticks, which makes them monospace and stops
Telegram from auto-linking them; `docker/agent/patches/telegram-help-clickable.py`
(applied by `setup.sh`, idempotent, survives a Hermes reinstall) strips those backticks
so the listed commands stay tappable.

### Branding & avatar

`scripts/setup-telegram-branding.sh` (run in the container) sets Daimon's bot name,
descriptions, and menu button via the Bot API. The command menu itself is managed
by Hermes.

The profile photo can only be set through **@BotFather → `/setuserpic`** (the Bot API
has no method for it). Upload one there — face-focused, so it still reads as a small
circular avatar.

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
  agent runs inside his own container where blackbox can't probe it.

Stop the sidecars with `docker compose --profile monitoring down`.

## Changing the model

1. Pull a tag with a ≥64K context window on your Ollama: `ollama pull llama3.1:8b`
2. Edit `config/config.yaml` → `model.default` (plus `context_length` and the
   `providers.custom.models` timeout key) to match.
3. `docker compose restart agent` — setup re-syncs the config on every start.

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
  which his container joins. That network is the isolation boundary: anything else on
  it can reach Daimon's sidecars. SearXNG and TTS also publish on the host
  (`localhost:8888` / `localhost:8880`) for convenience; on macOS
  SearXNG binds to loopback in the shared stack, so it is not reachable from the LAN.
- **Backups:** the `com.hermes.backup` launchd agent runs `scripts/backup-hermes.sh`
  daily, archiving the `hermes-data` volume to `~/hermes-backups`. Qdrant is a
  rebuildable index provided by your shared stack, so it is backed up there, not by Daimon.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and [SECURITY.md](../SECURITY.md) for
conventions and the security posture.
