# Project Overview

**Ella** — a local AI companion built on **Hermes Agent** (Nous Research CLI agent).
Hermes runs in a devcontainer; inference is served by **Ollama** running natively on
the macOS host. The repo is the local-first deployment (config + host services +
scripts) plus Ella's application code: a RAG knowledge base, a workflow engine, and a
web canvas.

# Architecture

- Ollama runs **natively on the macOS host** (Metal GPU); Hermes runs **in the
  devcontainer**. The container reaches Ollama at
  `host.docker.internal:11434/v1` (OpenAI-compatible API).
- Rationale: Ollama inside Docker on macOS is CPU-only; native host keeps
  inference Metal-accelerated while Hermes stays sandboxed.
- Two named volumes persist across rebuilds: **`hermes-data`** (`~/.hermes`: config,
  memories, sessions, agent code) and **`hermes-local`** (`~/.local`: uv Python
  runtime + launcher). With both warm, `postCreate.sh` skips the Hermes install.
- `config/config.yaml` / `config/SOUL.md` are the source of truth; `postCreate.sh`
  syncs them into `~/.hermes/`.
- The container uses `overrideCommand: false`; its command `container-boot.sh` is
  PID 1 — it starts the messaging gateway (surviving, unlike a lifecycle hook) and
  then idles. Lifecycle hooks (postStartCommand) cannot keep a daemon alive here.

# Technical Standards

- **Model:** default is **OpenAI gpt-5.5** (`openai-api`, Responses API) with the
  local **`gpt-oss:20b`** as automatic fallback (`fallback_providers`). Alternate
  profiles: `ollama` (local) and `claude-max` (Claude subscription). Vision stays
  local `qwen2.5vl:7b`; embeddings `nomic-embed-text` (768-dim). See ADR-0014.
- **Ollama install:** official `ollama-app` Homebrew cask (Metal runner), bound to
  `0.0.0.0`, with `OLLAMA_CONTEXT_LENGTH=65536`, flash attention, `q8_0` KV cache.
- **Devcontainer:** Debian base; Hermes installed via the official installer into
  the persisted volume. `~/.local/bin` on PATH via Dockerfile `ENV`.
- Documentation follows the `documentation-minimalism` skill: intent over
  mechanics, no negative guidance, no code-restating comments.

# Integrations

- **Ollama** (`/v1`) serves chat (`gpt-oss:20b`) and vision (`qwen2.5vl:7b`); the
  `vision` toolset points at the latter.
- **Web search** uses a local **SearXNG** on the host (`host.docker.internal:8888`,
  `SEARXNG_URL`), started by `scripts/setup-searxng-host.sh`.
- **Telegram** via the messaging gateway (`hermes gateway run`); `TELEGRAM_BOT_TOKEN`
  in `~/.hermes/.env`, restricted to paired users. Runs only while the gateway
  process and container are up.
- **Identity** is set by `config/SOUL.md`, synced to `~/.hermes/SOUL.md`. Ella speaks
  in the **first person**; the framework is infrastructure, never identity.
- **Voice:** local both ways. TTS = Kokoro-FastAPI (`tts/`, `host.docker.internal:8880`)
  via the `openai` provider; STT = faster-whisper. Telegram: `/voice on` replies in
  audio on voice input (the gateway gate fires only on `message_type == VOICE`, so
  text-in stays text-out — left as-is). Web: `/api/tts` (🔊/auto-speak) and `/api/stt`
  (🎙 record→transcribe, model cached in the volume). See ADR-0010.
- **Telegram sessions:** one session per DM, reset after 30 min idle via
  `config/gateway.json` (`reset_by_platform.telegram.idle_minutes`); seeded by
  postCreate if absent. `/new` resets on demand. Durable memory is separate.
- **Knowledge base (RAG):** `ingestion/ella_kb` package + **Qdrant** host service
  (`host.docker.internal:6333`, API key in `~/.hermes/.env`). One collection per
  enabled source type (`kb_<type>__nomic768`); pluggable **adapters** (`files`,
  `urls`, `chat` on; `feeds`/`webhook` example connectors off). SQLite **ledger** in
  hermes-data is the source of truth; Qdrant is rebuildable. Exposed to Ella via the
  `ella-kb` **MCP server** (capture/recall/forget/list_recent) + the `knowledge-base`
  skill; installed into the Hermes venv by `postCreate.sh`. **Feeds** use a host
  **Miniflux** (`miniflux/`, optional). See ADR-0009 and `ingestion/README.md`.
- **Skills** (`config/skills/`, synced to `~/.hermes/skills/`, each a `/command`):
  `status`, `knowledge-base`, `feeds-digest`.
- **Kanban / profiles:** the dispatcher runs inside the gateway, which now starts
  even without Telegram (`start-gateway.sh`); `ready` tasks **with an assignee** spawn
  on the next tick. The assignee is a **profile** (a separate `~/.hermes/profiles/<n>`
  home). Versioned in `config/profiles/`, synced by `postCreate` (which creates each
  and propagates the creds each needs into its isolated `.env`):
  - `default` — OpenAI **gpt-5.5** (`openai-api`, Responses API) + local Ollama
    fallback. The provider reads `OPENAI_API_KEY`/`OPENAI_BASE_URL` from the env (not
    config); postCreate writes them into `~/.hermes/.env` from `OPENAI_PROFILE_API_KEY`.
    Must be a **reasoning** model (gpt-5.x/o-series) — encrypted reasoning content.
  - `ollama` — local `gpt-oss:20b`, no API cost.
  - `claude-max` — Claude subscription (`anthropic`, `claude-sonnet-4-5`); OAuth from
    `CLAUDE_CODE_OAUTH_TOKEN`. Named `claude-max` so its launcher doesn't clobber the
    `claude` CLI. **Needs a Max plan with extra usage credits** (else HTTP 400 "out of
    extra usage"); the base allowance isn't usable via Hermes.
  Telegram creds are propagated to each profile's `.env` so task agents can
  `hermes send` results. See ADR-0013 and ADR-0014.
- **Proactivity & UX** (config.yaml): a daily **`morning-briefing`** cron (Ella's
  anticipation) runs on the `default` profile and delivers to the Telegram home channel
  (postCreate creates it when Telegram is set; the gateway's scheduler fires it). The
  **memory `curator`** runs weekly to archive stale memories (backups kept). `stt` local
  (faster-whisper) for voice-in; `human_delay: natural` for human pacing;
  `unauthorized_dm_behavior: ignore`; a `/health` quick command pings host services.
- **Web dashboard** (`hermes dashboard`): needs the `[web,pty]` extras and Node (both
  wired into the container build — `postCreate` + the `node` devcontainer feature). The
  frontend builds on first launch into the hermes-data volume. Loopback bind has no
  auth gate; `--host 0.0.0.0` requires `--insecure` or an auth provider.
- **Web layer + workflows:** `ingestion/ella_flow` (typed node-graph engine — nodes
  are Ella's capabilities; solid flow edges vs dotted resource edges) + `ingestion/
  ella_web` (FastAPI `ella-web` on :8099: catalog, workflow CRUD, run via REST/WS,
  chat) + `web/frontend` (React + React Flow canvas). Installed into the Hermes venv
  by `postCreate` extras `[mcp,feeds,web]`. New node types drop in via the registry
  or an `ella_flow.nodes` entry point. Telegram bot unchanged. See ADR-0011 and
  `web/README.md`. gRPC deferred.
- **Monitoring** (`monitoring/`): Grafana+Loki+Promtail+Prometheus+blackbox on the
  host. Grafana is **loopback-only** at `localhost:3000`. Promtail ships Hermes
  logs (hermes-data volume) and the Ollama log (`~/.hermes-monitoring/ollama.log`).
  Prometheus/blackbox probe up/down; an "Ollama down" alert DMs Telegram
  (`monitoring/.env` + generated `contactpoints.yaml`, both gitignored). No
  docker.sock mount (security). A `chat-shipper` sidecar reads Hermes' `state.db`
  (conversation `messages`) and ships the real text to Loki for the chat panel.
- **Redis** (`redis/`): single shared, password-protected, loopback-only
  (`127.0.0.1:6379`) instance on the external `hermes-shared` Docker network.
  Backs SearXNG's cache/limiter (db 1) and is open for current/future containers
  (db 0). Valkey was consolidated into it. Password in `redis/.env` (gitignored);
  start Redis before SearXNG.
- **Host services** are optional user-installed launchd agents
  (`scripts/install-host-services.sh`): Ollama as a managed service, stacks
  autostart, daily backup. Run by the user (persistence needs explicit consent).
- **Security posture:** approvals **manual** across profiles (the kanban dispatcher
  runs tasks headless and bypasses approvals on its own), `redact_secrets`, Tirith
  **fail-closed**.
  Ollama/SearXNG must bind `0.0.0.0` (container reaches them via
  host.docker.internal); LAN exposure is mitigated by `scripts/firewall-host.sh`
  (user-run, sudo).

# Known Constraints

- Hermes **requires a model with ≥64K context**. Models capping below that are
  rejected at startup (`qwen3:8b` maxes at 40,960 on Ollama and cannot extend
  without re-converting the GGUF with YaRN).
- Ollama must bind **`0.0.0.0`** (not `127.0.0.1`) for the container to reach it.
- Model must fit the host's ~17.8 GiB Metal VRAM budget to stay 100% on GPU.
- macOS-host-specific: Homebrew cask, `launchctl setenv`, `host.docker.internal`.

Major decisions are recorded in `DECISIONS.md`.
