# Project Overview

**Daimon** — an AI companion built on **Hermes Agent** (Nous Research CLI agent).
Hermes runs in his own container, brought up by docker-compose; the default model is
the local **Ollama** `gpt-oss:20b`, with **OpenAI gpt-5-mini** as an optional fallback. The repo is the
deployment (config + sidecars + scripts) plus Daimon's application code: a RAG
knowledge base and a headless workflow engine.

Daimon runs on a **shared infra stack the operator provides**, not one it declares.

# Architecture

- **Shared infra is external and not Daimon's to declare** (Ollama, Qdrant, Redis,
  observability). It lives on an external Docker network — `SHARED_NETWORK`, default
  `shared` — and Daimon reaches it by DNS: `ollama:11434`, `qdrant:6333`, `redis:6379`,
  `loki:3100`, `grafana:3000`. That stack must be up first, or the network does not exist.
- Daimon adds only his **own sidecars** (`searxng`, `tts`) plus telemetry, all on that
  network with a **`daimon-`** alias (`daimon-searxng:8080`, `daimon-tts:8880`) so generic
  names stay collision-free next to other stacks. Profile `core`, via `make up`.
- The **agent container** (compose service `agent`, profile `core`) joins the same
  network, which is how Hermes reaches both the shared services and the sidecars. The
  optional dev container (`.devcontainer/`) joins it too (`runArgs`,
  `${localEnv:SHARED_NETWORK}`) and reuses the same image and `setup.sh`, without
  starting a gateway — two gateways on one `state.db` is one too many.
- Two named volumes persist across rebuilds: **`hermes-data`** (`~/.hermes`: config,
  memories, sessions, agent code) and **`hermes-local`** (`~/.local`: uv Python
  runtime + launcher). With both warm, `setup.sh` skips the Hermes install. Both are
  declared **external** in compose, because the dev container mounts them by name.
- `config/config.yaml` is the source of truth; `setup.sh` syncs it into `~/.hermes/`.
  The persona is the exception: the hub owns it and serves it at
  `GET /api/internal/persona` (`HUB_INTERNAL_URL` + `HUB_WORKER_TOKEN`), so `setup.sh`
  fetches it into the `SOUL.md` Hermes loads and falls back to `config/SOUL.md` only
  when the hub is unreachable — editing the repo copy no longer changes the running
  persona. `SOUL.md` is Hermes' loading mechanism, not the contract with the hub.
- `entrypoint.sh` is PID 1: it runs setup, starts the messaging gateway (surviving, as
  a child of PID 1) and then idles. A gateway needs an owner process — a lifecycle hook
  cannot keep a daemon alive.

# Technical Standards

- **Model:** default is the local **`gpt-oss:20b`** (`custom`, the shared Ollama) with
  **OpenAI gpt-5-mini** as an optional fallback (`fallback_providers`, `openai-api`,
  Responses API) — local-first, so no key is required to run. Alternate profiles:
  `ollama` (local, explicit) and `claude-max` (Claude subscription). Vision stays
  local `qwen2.5vl:7b`; embeddings `nomic-embed-text` (768-dim).
- **Ollama:** part of the shared stack, not Daimon's to install or tune. The models
  Daimon needs (`gpt-oss:20b`, `qwen2.5vl:7b`, `nomic-embed-text`) and the served window
  (`OLLAMA_CONTEXT_LENGTH`) are the operator's call; `make doctor` reports what is missing.
- **Agent image** (`docker/agent/`): Debian base; Hermes installed via the official
  installer into the persisted volume. `~/.local/bin` on PATH via Dockerfile `ENV`.
  `entrypoint.sh` (PID 1) runs `setup.sh`, then the gateway, then idles — a setup or
  gateway failure is loud in `docker logs` and never stops the container.
- Documentation follows the `documentation-minimalism` skill: intent over
  mechanics, no negative guidance, no code-restating comments.

# Integrations

- **Ollama** (`ollama:11434/v1`) serves chat (`gpt-oss:20b`) and vision (`qwen2.5vl:7b`);
  the `vision` toolset points at the latter.
- **Web search** uses Daimon's **SearXNG** sidecar (`daimon-searxng:8080`, `SEARXNG_URL`),
  whose cache/limiter is the shared Redis (db 5). Its `docker/searxng/settings.yml` is
  generated and gitignored — `make settings` creates it, and it must exist before any
  compose up.
- **Telegram** via the messaging gateway (`hermes gateway run`); `TELEGRAM_BOT_TOKEN`
  in `~/.hermes/.env`, restricted to paired users. Runs only while the gateway
  process and container are up.
- **Identity** comes from the hub's soul, fetched into `~/.hermes/SOUL.md` at every
  start (`config/SOUL.md` is the offline fallback). Daimon speaks in the **first
  person**; the framework is infrastructure, never identity.
- **Voice:** local both ways. TTS = Kokoro-FastAPI (`docker-compose.yml` `tts` service,
  `daimon-tts:8880`) via the `openai` provider; STT = faster-whisper. Telegram: `/voice on` replies in
  audio on voice input (the gateway gate fires only on `message_type == VOICE`, so
  text-in stays text-out — left as-is). Web: `/api/tts` (🔊/auto-speak) and `/api/stt`
  (🎙 record→transcribe, model cached in the volume).
- **Telegram sessions:** one session per DM, reset after 30 min idle via
  `config/gateway.json` (`reset_by_platform.telegram.idle_minutes`); seeded by
  setup.sh if absent. `/new` resets on demand. Durable memory is separate.
- **Knowledge base (RAG):** `ingestion/daimon_kb` package + the shared **Qdrant**
  (`qdrant:6333`, API key in `~/.hermes/.env`). One collection per
  enabled source type (`kb_<type>__nomic768`); pluggable **adapters** (`files`,
  `urls`, `chat` on; `feeds`/`webhook` example connectors off). SQLite **ledger** in
  hermes-data is the source of truth; Qdrant is rebuildable. Exposed to Daimon via the
  `daimon-kb` **MCP server** (capture/recall/forget/list_recent) + the `knowledge-base`
  skill; installed into the Hermes venv by `setup.sh`. **Feeds** need a **Miniflux**
  of your own, so the connector stays off unless `MINIFLUX_URL` is set. See
  `ingestion/README.md`.
- **Skills** (`config/skills/`, synced to `~/.hermes/skills/`, each a `/command`):
  `status`, `knowledge-base`, `feeds-digest`.
- **Kanban / profiles:** the dispatcher runs inside the gateway, which now starts
  even without Telegram (`start-gateway.sh`); `ready` tasks **with an assignee** spawn
  on the next tick. The assignee is a **profile** (a separate `~/.hermes/profiles/<n>`
  home). Versioned in `config/profiles/`, synced by `setup.sh` (which creates each
  and propagates the creds each needs into its isolated `.env`):
  - `default` — local **gpt-oss:20b** (`custom`, the shared Ollama) with an optional
    OpenAI **gpt-5-mini** fallback (`openai-api`, Responses API). That provider reads
    `OPENAI_API_KEY`/`OPENAI_BASE_URL` from the env (not config); `setup.sh` writes them
    into `~/.hermes/.env` from `OPENAI_PROFILE_API_KEY`, taken from the file or, failing
    that, the environment (compose passes the repo `.env` through). Must be a
    **reasoning** model (gpt-5.x/o-series) — encrypted reasoning content.
  - `ollama` — local `gpt-oss:20b`, no API cost.
  - `claude-max` — Claude subscription (`anthropic`, `claude-sonnet-4-5`); OAuth from
    `CLAUDE_CODE_OAUTH_TOKEN`. Named `claude-max` so its launcher doesn't clobber the
    `claude` CLI. **Needs a Max plan with extra usage credits** (else HTTP 400 "out of
    extra usage"); the base allowance isn't usable via Hermes.
  Telegram creds are propagated to each profile's `.env` so task agents can
  `hermes send` results.
- **Proactivity & UX** (config.yaml): a daily **`morning-briefing`** cron (Daimon's
  anticipation) runs on the `default` profile and delivers to the Telegram home channel
  (setup.sh creates it when Telegram is set; the gateway's scheduler fires it). The
  **memory `curator`** runs weekly to archive stale memories (backups kept). `stt` local
  (faster-whisper) for voice-in; `human_delay: natural` for human pacing;
  `unauthorized_dm_behavior: ignore`; a `/health` quick command pings host services.
- **Web dashboard** (`hermes dashboard`): needs the `[web,pty]` extras and Node (both
  wired into the container build — `setup.sh` + nodesource in the Dockerfile). Compose
  publishes `127.0.0.1:8090` for it. The frontend builds on first launch into the
  hermes-data volume. Loopback bind has no
  auth gate; `--host 0.0.0.0` requires `--insecure` or an auth provider.
- **Workflows (headless):** `ingestion/daimon_flow` (typed node-graph engine — nodes
  are Daimon's capabilities; solid flow edges vs dotted resource edges). Workflows are
  defined in config/code and run programmatically, with no server or UI. Installed into
  the Hermes venv by `setup.sh` extras `[mcp,feeds]`. New node types drop in via the
  registry or a `daimon_flow.nodes` entry point. Telegram bot unchanged.
  gRPC deferred.
- **Monitoring:** the observability plane (Grafana/Loki/Prometheus) belongs to the shared
  stack. Daimon keeps only two app-level telemetry sidecars in the root
  `docker-compose.yml` (`monitoring` profile): `chat-shipper` reads Hermes' `state.db`
  (conversation `messages`) and ships the real text to `loki:3100` for the chat panel;
  `status-exporter` exposes `hermes_gateway_up` (from `agent.log`) at
  `daimon-status-exporter:9101/metrics` for the shared Prometheus.
- **Redis:** shared (`redis:6379`, passwordless). SearXNG's cache/limiter uses **db 5** —
  one index out of whatever map the operator's stack keeps.
- **Host services** are optional user-installed launchd agents
  (`scripts/install-host-services.sh`): autostart and daily backup. macOS-only, and
  run by the user (persistence needs explicit consent).
- **Security posture:** approvals **manual** across profiles (the kanban dispatcher
  runs tasks headless and bypasses approvals on its own), `redact_secrets`, Tirith
  **fail-closed**. Daimon's sidecars sit on a shared network, so anything else on it can
  reach them — the isolation boundary is the network, not the port.

# Known Constraints

- Hermes **requires a model with ≥64K context**. Models capping below that are
  rejected at startup (`qwen3:8b` maxes at 40,960 on Ollama and cannot extend
  without re-converting the GGUF with YaRN).
- A shared Ollama serves **one `OLLAMA_CONTEXT_LENGTH` to all its consumers** (a model
  can override it with a baked `num_ctx`). If it is set below 64K, or Daimon's models are
  not pulled there, the local paths — now including the default model — fail, and only
  the OpenAI fallback still answers. Changing either affects every consumer, so it is the
  operator's call, not Daimon's — `make doctor` reports the gap rather than papering over
  it.
- `model.context_length` must equal what Ollama **actually serves**. Claiming more does
  not error: Hermes budgets a window the server truncates, and the failure surfaces as
  replies cut short mid-sentence, which reads like a model quality problem rather than a
  config one.
- The **shared network must exist** before anything here starts, dev container included.
- Legacy macOS-host assumptions still live in `scripts/` (Homebrew cask, `launchctl`,
  `pfctl`): `setup-ollama-host.sh`, `install-host-services.sh`, `firewall-host.sh`,
  `install-firewall-daemon.sh`. Inert on a Linux host.
