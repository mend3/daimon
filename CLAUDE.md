# Hermes Agent — Local Setup

This repo runs **Daimon** — an AI companion built on **Hermes Agent** — in a
devcontainer. It defaults to **OpenAI gpt-5-mini** with a fully-local **Ollama**
(`gpt-oss:20b`) profile + automatic fallback, so it can run cloud-default or fully
local. It is the deployment (config + sidecars + scripts) plus Daimon's own
application code: a RAG knowledge base and a headless workflow engine (`ingestion/`).

Daimon depends on a **shared infra stack you provide** — Ollama, Qdrant, Redis and an
observability plane — reached by DNS on an external Docker network (`SHARED_NETWORK`,
default `shared`): `ollama:11434`, `qdrant:6333`, `redis:6379`, `loki:3100`,
`grafana:3000`. Daimon declares none of them; it adds only its own sidecars (SearXNG,
TTS) and the devcontainer where Hermes runs. **Start that stack first** — without the
network, nothing here can attach.

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
| `config/` | Source of truth synced to `~/.hermes/`: `config.yaml`, `SOUL.md` (persona), `daimon_kb.yaml`, `gateway.json`, `skills/`, `.env.example` |
| `ingestion/` | Daimon's Python: `daimon_kb` (RAG), `daimon_flow` (headless workflow engine) |
| `docker-compose.yml` | Daimon's sidecars (searxng, tts, telemetry) with profiles, on the shared network |
| `docker/` | Container configs: `searxng/`, `chat-shipper/`, `status-exporter/` |
| `scripts/` | Setup + lifecycle (sidecars, backup, doctor; the launchd/firewall ones are macOS-only) |
| `README.md` / `docs/setup.md` | Product overview / setup & operations guide |

## How to run

1. **Shared infra:** start your stack (Ollama, Qdrant, Redis + observability) on the
   external network named by `SHARED_NETWORK`.
2. **Sidecars:** `make up` — searxng + tts (profile `core`) on that network.
3. **Preflight:** `make doctor` — probes the models and services from inside the network.
4. **Container:** open the folder in a Dev Containers client, or `make devcontainer`.
   `postCreate.sh` installs Hermes and syncs config.
5. **Use:** inside the container, `hermes`. Inspect with `hermes config`, diagnose
   with `hermes doctor`.

## Invariants — keep these true

- The default model is **OpenAI gpt-5-mini** (`openai-api` provider, Responses API), so
  `OPENAI_PROFILE_API_KEY` must be set in `~/.hermes/.env`; postCreate writes it to
  `OPENAI_API_KEY`/`OPENAI_BASE_URL`, which that provider reads from the env.
- Any **local** model (the `ollama` profile, the fallback, vision) must expose a
  **≥64K context window** to Ollama; Hermes rejects less. The shared Ollama sets
  `OLLAMA_CONTEXT_LENGTH` for all of its consumers, so that window is your stack's call,
  not Daimon's — as are the model pulls (`gpt-oss:20b`, `qwen2.5vl:7b`,
  `nomic-embed-text`). `make doctor` reports what is missing.
- Shared infra is **yours to declare**, never Daimon's: no Ollama/Qdrant/Redis or
  observability service belongs in this repo's compose. Daimon consumes them by DNS.
- Daimon's own services carry a **`daimon-`** alias on the shared network
  (`daimon-searxng:8080`, `daimon-tts:8880`), keeping generic names collision-free
  next to other stacks on it.
- The devcontainer joins the same network (`runArgs`), which is how Hermes reaches both
  the shared services and the sidecars.
- `config/config.yaml` is the source of truth; `postCreate.sh` copies it into
  `~/.hermes/config.yaml`. Edit the repo copy, not the runtime copy.
- Secrets live only in `~/.hermes/.env` (seeded from `config/.env.example`) and are
  never committed.
- `docker/searxng/settings.yml` is generated and gitignored; `make settings` creates it.
  It must exist before any compose up of searxng.

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
- **devcontainer** — the isolated container where Hermes and its tools execute; it
  joins the shared network.
- **`hermes-data` / `hermes-local`** — named volumes persisting `~/.hermes/` and
  `~/.local/` (toolchain) across rebuilds.
- **`~/.hermes/`** — Hermes' runtime home: `config.yaml`, `.env`, `SOUL.md`
  (agent identity), `memories/`, `sessions/`, `logs/`, and `state.db` (conversations).
- **shared network** — the external Docker network your infra stack owns (`SHARED_NETWORK`,
  default `shared`); where Daimon meets Ollama, Qdrant, Redis, observability and her own
  sidecars.
- **chat-shipper** — sidecar that ships `state.db` conversation text to Loki for the
  Grafana chat panel.
