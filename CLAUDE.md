# Hermes Agent — Local Setup

This repo runs **Daimon** — an AI companion built on **Hermes Agent** — in his own
container, brought up by docker-compose. He defaults to the fully-local **Ollama**
(`gpt-oss:20b`) with **OpenAI gpt-5-mini** as an optional fallback, so he runs fully
local out of the box and reaches for the cloud only when you give him a key. It is the
deployment (config + sidecars + scripts) plus Daimon's own application code: a RAG
knowledge base and a headless workflow engine (`ingestion/`).

Daimon depends on a **shared infra stack you provide** — Ollama, Qdrant, Redis and an
observability plane — reached by DNS on an external Docker network (`SHARED_NETWORK`,
default `shared`): `ollama:11434`, `qdrant:6333`, `redis:6379`, `loki:3100`,
`grafana:3000`, `searxng:8080`, `tts:8880`. Daimon declares none of them; it adds only
TTS) and the container Hermes runs in. **Start that stack first** — without the
network, nothing here can attach.

## What Hermes is, and when to use it

Hermes Agent (Nous Research) is a CLI AI agent with tool calling — shell, files,
web, memory, cron, messaging gateways. The default profile runs the local
**`gpt-oss:20b`**, falling back to **OpenAI gpt-5-mini** when it errors out (optional —
needs a key). Two alternate profiles ship alongside: **`ollama`** (local, explicit) and
**`claude-max`** (your Claude subscription). Switch with `hermes model` or per profile.
Talk to him with `docker compose exec agent hermes`.

## Repository map

| Path | Purpose |
|------|---------|
| `.claude/CLAUDE.md` | Memory policy — how to maintain the files below |
| `.claude/MEMORY.md` | Durable project knowledge (architecture, standards, constraints) |
| `.claude/SESSION.md` | Ephemeral session context (gitignored) |
| `.claude/skills/documentation-minimalism/` | Writing standard for all docs and comments |
| `docker/agent/` | The container Hermes runs in: Dockerfile, `entrypoint.sh`, `setup.sh` |
| `.devcontainer/` | Optional dev shell for editing this repo — same image + `setup.sh`, no gateway |
| `config/` | Source of truth synced to `~/.hermes/`: `config.yaml`, `daimon_kb.yaml`, `gateway.json`, `skills/`, `.env.example` — plus `SOUL.md`, which is only the offline fallback for the persona the hub serves |
| `ingestion/` | Daimon's Python: `daimon_kb` (RAG), `daimon_flow` (headless workflow engine) |
| `docker-compose.yml` | Daimon + his telemetry sidecars, with profiles, on the shared network |
| `docker/` | Container configs: `chat-shipper/`, `status-exporter/` |
| `scripts/` | Setup + lifecycle (sidecars, backup, doctor; the launchd/firewall ones are macOS-only) |
| `README.md` / `docs/setup.md` | Product overview / setup & operations guide |

## How to run

1. **Shared infra:** start your stack (Ollama, Qdrant, Redis + observability) on the
   external network named by `SHARED_NETWORK`.
2. **Preflight:** `make doctor` — probes the models and services from inside the network.
3. **Up:** `make up` — Daimon (profile `core`) on that network. On the
   agent, `setup.sh` installs Hermes and syncs config, then the entrypoint starts the
   gateway; `make agent` does just that service.
4. **Use:** `docker compose exec agent hermes`. Inspect with `hermes config`, diagnose
   with `hermes doctor`. To edit the repo itself: `make devcontainer`.

## Invariants — keep these true

- The default model is the local **`gpt-oss:20b`**, and `model.context_length` must
  equal what your Ollama actually serves — claim more and Hermes budgets a window the
  server truncates, which surfaces as replies cut short, not as an error. The OpenAI
  fallback is optional: set `OPENAI_PROFILE_API_KEY` (in `~/.hermes/.env` or the repo
  `.env`, which compose passes through) and `setup.sh` writes `OPENAI_API_KEY`/
  `OPENAI_BASE_URL`, which the `openai-api` provider reads from the env.
- Any **local** model (the `ollama` profile, the fallback, vision) must expose a
  **≥64K context window** to Ollama; Hermes rejects less. The shared Ollama sets
  `OLLAMA_CONTEXT_LENGTH` for all of its consumers, so that window is your stack's call,
  not Daimon's — as are the model pulls (`gpt-oss:20b`, `qwen2.5vl:7b`,
  `nomic-embed-text`). `make doctor` reports what is missing.
- Shared infra is **yours to declare**, never Daimon's: no Ollama/Qdrant/Redis or
  observability service belongs in this repo's compose. Daimon consumes them by DNS.
- Daimon's own services carry a **`daimon-`** alias on the shared network
  keeping generic names collision-free
  next to other stacks on it.
- Daimon's container joins the same network, which is how Hermes reaches both the
  shared services and the sidecars. The dev container joins it too (`runArgs`).
- `config/config.yaml` is the source of truth; `setup.sh` copies it into
  `~/.hermes/config.yaml` on every container start. Edit the repo copy, not the runtime
  copy, then `docker compose restart agent`.
- **The persona is not ours.** The hub owns it and serves it at
  `GET /api/internal/persona`; `setup.sh` fetches it into `~/.hermes/SOUL.md` with
  `HUB_INTERNAL_URL` + `HUB_WORKER_TOKEN`. `SOUL.md` is Hermes' way of loading a
  persona, not the contract — the hub ships text, this repo writes the file. So
  `config/SOUL.md` is only the offline fallback, and editing it does not change a
  running Daimon that can reach the hub. Leaving both env vars unset is supported and
  pins him to the fallback.
- Secrets live only in `~/.hermes/.env` (seeded from `config/.env.example`) and are
  never committed.
- **Search and voice are NOT declared here.** They moved to the shared stack (the oracle),
  reached by DNS at `searxng:8080` and `tts:8880`. Two stacks each publishing host port
  8888 cannot coexist, and neither is a feature of this agent.

## Conventions

- All documentation and comments follow the `documentation-minimalism` skill.
- After durable changes, update `.claude/MEMORY.md` per the policy in
  `.claude/CLAUDE.md`. Keep `.claude/SESSION.md` for transient state.

## Glossary

- **Hermes Agent** — Nous Research CLI agent with tool calling; the thing this repo runs.
- **Ollama** — local model server; exposes an OpenAI-compatible `/v1` API.
- **gpt-oss:20b** — the local model (MoE, ~3.6B active): the default and the `ollama`
  profile.
- **gpt-5-mini** — the optional fallback (OpenAI, reasoning, via the openai-api provider).
- **Profiles** — `default` (local gpt-oss:20b + OpenAI fallback), `ollama` (local,
  explicit), `claude-max` (Claude subscription); each a separate `~/.hermes` home.
- **agent container** — the isolated container where Hermes and its tools execute
  (compose service `agent`); it joins the shared network.
- **`hermes-data` / `hermes-local`** — named volumes persisting `~/.hermes/` and
  `~/.local/` (toolchain) across rebuilds.
- **`~/.hermes/`** — Hermes' runtime home: `config.yaml`, `.env`, `SOUL.md`
  (agent identity), `memories/`, `sessions/`, `logs/`, and `state.db` (conversations).
- **shared network** — the external Docker network your infra stack owns (`SHARED_NETWORK`,
  default `shared`); where Daimon meets Ollama, Qdrant, Redis, observability and his own
  sidecars.
- **chat-shipper** — sidecar that ships `state.db` conversation text to Loki for the
  Grafana chat panel.
