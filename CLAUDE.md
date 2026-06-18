# Hermes Agent — Local Setup

This repo runs **Ella** — an AI companion built on **Hermes Agent** — in a
devcontainer. It defaults to **OpenAI gpt-5-mini** with a fully-local **Ollama**
(`gpt-oss:20b`, Metal GPU) profile + automatic fallback, so it can run cloud-default
or fully local. It is the deployment (config + host services + scripts) plus Ella's
own application code: a RAG knowledge base, a workflow engine, and a web canvas
(`ingestion/`, `web/`).

## What Hermes is, and when to use it

Hermes Agent (Nous Research) is a CLI AI agent with tool calling — shell, files,
web, memory, cron, messaging gateways. The default profile runs **OpenAI gpt-5-mini**
(needs an OpenAI key) with the local **`gpt-oss:20b`** as an automatic fallback. Two
alternate profiles ship alongside: **`ollama`** (fully local/offline) and
**`claude-max`** (your Claude subscription). Switch with `hermes model` or per
profile. Start it inside the devcontainer with `hermes`.

## Repository map

| Path | Purpose |
|------|---------|
| `.claude/CLAUDE.md` | Memory policy — how to maintain the files below |
| `.claude/MEMORY.md` | Durable project knowledge (architecture, standards, constraints) |
| `.claude/DECISIONS.md` | ADRs — major decisions and their rationale |
| `.claude/SESSION.md` | Ephemeral session context (gitignored) |
| `.claude/skills/documentation-minimalism/` | Writing standard for all docs and comments |
| `.devcontainer/` | Container definition, Dockerfile, `postCreate.sh` |
| `config/` | Source of truth synced to `~/.hermes/`: `config.yaml`, `SOUL.md` (persona), `ella_kb.yaml`, `gateway.json`, `skills/`, `.env.example` |
| `ingestion/` | Ella's Python: `ella_kb` (RAG), `ella_flow` (workflow engine), `ella_web` (FastAPI) |
| `web/` | React Flow web canvas — frontend + Dockerized backend (`make web`) |
| `docker-compose.yml` | All host sidecars (searxng, tts, web, telemetry) with profiles |
| `docker/` | Container configs: `searxng/`, `chat-shipper/`, `status-exporter/` |
| `scripts/` | Host setup + lifecycle (Ollama, services, backup, firewall) |
| `README.md` / `docs/setup.md` | Product overview / setup & operations guide |

## How to run

1. **Host:** `./scripts/setup-ollama-host.sh` — installs Ollama (Metal) and pulls
   the model, served on `0.0.0.0:11434` at a 64K window.
2. **Container:** open the folder in a Dev Containers client, or
   `devcontainer up --workspace-folder .`. `postCreate.sh` installs Hermes and
   syncs config.
3. **Use:** inside the container, `hermes`. Inspect with `hermes config`, diagnose
   with `hermes doctor`.

## Invariants — keep these true

- The default model is **OpenAI gpt-5-mini** (`openai-api` provider, Responses API), so
  `OPENAI_PROFILE_API_KEY` must be set in `~/.hermes/.env`; postCreate writes it to
  `OPENAI_API_KEY`/`OPENAI_BASE_URL`, which that provider reads from the env.
- Any **local** model (the `ollama` profile, the fallback, vision) must expose a
  **≥64K context window** to Ollama; Hermes rejects less.
- Ollama binds **`0.0.0.0`** on the host so the container reaches it at
  `host.docker.internal:11434/v1` (fallback, vision, and embeddings).
- `config/config.yaml` is the source of truth; `postCreate.sh` copies it into
  `~/.hermes/config.yaml`. Edit the repo copy, not the runtime copy.
- Secrets live only in `~/.hermes/.env` (seeded from `config/.env.example`) and are
  never committed.

## Conventions

- All documentation and comments follow the `documentation-minimalism` skill.
- After durable changes, update `.claude/MEMORY.md` and `.claude/DECISIONS.md` per
  the policy in `.claude/CLAUDE.md`. Keep `.claude/SESSION.md` for transient state.

## Glossary

- **Hermes Agent** — Nous Research CLI agent with tool calling; the thing this repo runs.
- **Ollama** — local model server; exposes an OpenAI-compatible `/v1` API.
- **gpt-5-mini** — the default model (OpenAI, reasoning, via the openai-api provider).
- **gpt-oss:20b** — the local model (MoE, ~3.6B active): the `ollama` profile + the
  default's automatic fallback.
- **Profiles** — `default` (OpenAI gpt-5-mini + Ollama fallback), `ollama` (local),
  `claude-max` (Claude subscription); each a separate `~/.hermes` home.
- **Metal** — Apple's GPU backend; why Ollama runs on the host, not in Docker.
- **devcontainer** — the isolated container where Hermes and its tools execute.
- **host.docker.internal** — DNS name the container uses to reach the host's Ollama.
- **`hermes-data` / `hermes-local`** — named volumes persisting `~/.hermes/` and
  `~/.local/` (toolchain) across rebuilds.
- **`~/.hermes/`** — Hermes' runtime home: `config.yaml`, `.env`, `SOUL.md`
  (agent identity), `memories/`, `sessions/`, `logs/`, and `state.db` (conversations).
- **`hermes-shared`** — Docker network linking host containers to the shared Redis.
- **chat-shipper** — sidecar that ships `state.db` conversation text to Loki for the
  Grafana chat panel.
