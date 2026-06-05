# Hermes Agent — Local Setup (Ollama + gpt-oss, devcontainer)

Run [Hermes Agent](https://hermes-agent.nousresearch.com/docs/) fully isolated in a
**devcontainer**, driven by **gpt-oss:20b** served locally by **Ollama** running
natively on the macOS host (so inference uses the Apple Silicon GPU via Metal).

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
  devcontainer.json   # container def: volume, host networking, env, postCreate
  Dockerfile          # Debian base + git/curl/ripgrep/ffmpeg
  postCreate.sh       # installs Hermes, syncs config, checks Ollama reachability
config/
  config.yaml         # Hermes config → mounted to ~/.hermes/config.yaml
  SOUL.md             # agent identity/voice → mounted to ~/.hermes/SOUL.md
  .env.example        # secrets/env template
searxng/
  docker-compose.yml  # local web-search engine for the web toolset
  settings.yml.example
scripts/
  setup-ollama-host.sh   # HOST: install Ollama + pull chat & vision models
  setup-searxng-host.sh  # HOST: start local SearXNG
```

## Setup

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

### 2. (Optional) Start local web search

```bash
./scripts/setup-searxng-host.sh
```

Runs a private SearXNG on `localhost:8888` for the `web` toolset. The container
reaches it at `host.docker.internal:8888` (set as `SEARXNG_URL`).

### 3. Open the devcontainer

In VS Code (with the **Dev Containers** extension) or the `devcontainer` CLI:

- **VS Code:** open this folder → "Reopen in Container".
- **CLI:** `devcontainer up --workspace-folder .`

On first create, `postCreate.sh` installs Hermes, copies `config/config.yaml`
and `config/SOUL.md` into `~/.hermes/`, and verifies Ollama is reachable.

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
| Web search | local SearXNG | `./scripts/setup-searxng-host.sh` |
| Telegram | gateway → `TELEGRAM_BOT_TOKEN` | see below |
| Identity / voice | `config/SOUL.md` | edit + rebuild |

### Telegram

Create a bot with [@BotFather](https://t.me/BotFather), then inside the container:

```bash
hermes gateway setup          # paste the token, pair your account
hermes gateway run            # foreground; keep this terminal open
```

The bot answers only paired users (`TELEGRAM_ALLOWED_USERS`). The token lives in
`~/.hermes/.env`, never in the repo. The gateway runs only while `gateway run` is
active and the container is up.

## Changing the model

1. Pull a tag with a ≥64K context window on the host: `ollama pull llama3.1:8b`
2. Edit `config/config.yaml` → `model.default` (and the `providers.custom.models`
   timeout key) to match.
3. Rebuild the container (or `cp config/config.yaml ~/.hermes/config.yaml` inside it).

## What persists

`~/.hermes/` (config, `memories/`, `sessions/`, `skills/`, `logs/`, and the
installed agent code) lives in the **`hermes-data`** named Docker volume, so it
survives rebuilds. Delete it with `docker volume rm hermes-data` for a clean slate.

## Notes

- **Secrets:** real secrets go in `~/.hermes/.env` inside the container (seeded
  from `config/.env.example`). `config/.env` is git-ignored.
- **Web search** is off by default (no API keys). To enable, set a backend in
  `config.yaml` and the matching key in `.env` — e.g. a local SearXNG via
  `SEARXNG_URL=http://host.docker.internal:8080`.
- **No host filesystem access:** the agent's terminal backend is `local`, scoped
  to the container only.
