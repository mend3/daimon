# Hermes Agent — Local Setup

This repo configures and runs **Hermes Agent** locally: the agent runs isolated in
a devcontainer and talks to a model served by **Ollama** running natively on the
macOS host (Metal GPU). It is configuration + scripts, not application code.

## What Hermes is, and when to use it

Hermes Agent (Nous Research) is a CLI AI agent with tool calling — shell, files,
web, memory, cron, messaging gateways. This setup runs it fully local against
`gpt-oss:20b`, so no hosted API or key is needed. Reach for it to drive agentic
tasks from a local model. Start it inside the devcontainer with `hermes`.

## Repository map

| Path | Purpose |
|------|---------|
| `.claude/CLAUDE.md` | Memory policy — how to maintain the files below |
| `.claude/MEMORY.md` | Durable project knowledge (architecture, standards, constraints) |
| `.claude/DECISIONS.md` | ADRs — major decisions and their rationale |
| `.claude/SESSION.md` | Ephemeral session context (gitignored) |
| `.claude/skills/documentation-minimalism/` | Writing standard for all docs and comments |
| `.devcontainer/` | Container definition, Dockerfile, `postCreate.sh` |
| `config/config.yaml` | Hermes config — source of truth, synced to `~/.hermes/` |
| `config/.env.example` | Secrets template, seeds `~/.hermes/.env` |
| `scripts/setup-ollama-host.sh` | Host-side: install Ollama, pull the model |
| `README.md` | Human-facing setup guide |

## How to run

1. **Host:** `./scripts/setup-ollama-host.sh` — installs Ollama (Metal) and pulls
   the model, served on `0.0.0.0:11434` at a 64K window.
2. **Container:** open the folder in a Dev Containers client, or
   `devcontainer up --workspace-folder .`. `postCreate.sh` installs Hermes and
   syncs config.
3. **Use:** inside the container, `hermes`. Inspect with `hermes config`, diagnose
   with `hermes doctor`.

## Invariants — keep these true

- The model must expose a **≥64K context window** to Ollama; Hermes rejects less.
- Ollama binds **`0.0.0.0`** on the host so the container reaches it at
  `host.docker.internal:11434/v1`.
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
- **gpt-oss:20b** — the default model (MoE, ~3.6B active, 128K native context).
- **Metal** — Apple's GPU backend; why Ollama runs on the host, not in Docker.
- **devcontainer** — the isolated container where Hermes and its tools execute.
- **host.docker.internal** — DNS name the container uses to reach the host's Ollama.
- **`hermes-data`** — named Docker volume persisting `~/.hermes/` across rebuilds.
- **`~/.hermes/`** — Hermes' runtime home: `config.yaml`, `.env`, `SOUL.md`
  (agent identity), `memories/`, `sessions/`, `skills/`, `logs/`.
