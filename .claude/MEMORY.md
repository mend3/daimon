# Project Overview

Local, isolated setup for **Hermes Agent** (Nous Research CLI agent). Hermes runs
in a devcontainer; inference is served by **Ollama** running natively on the macOS
host. This repo is configuration + scripts, not application code.

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

- **Model:** `gpt-oss:20b` (MoE, ~3.6B active), served at a **64K context window**.
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
- **Identity** is set by `config/SOUL.md`, synced to `~/.hermes/SOUL.md`.
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
- **Security posture:** approvals manual, `redact_secrets`, Tirith **fail-closed**.
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
