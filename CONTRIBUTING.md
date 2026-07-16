# Contributing

This repo is the deployment for running Hermes Agent (Docker Compose)
**plus Daimon's own application code** — the RAG knowledge base and the headless
workflow engine under `ingestion/` (Python).

## Setup

You need macOS with Docker Desktop and Homebrew. `make up` brings up the host
services; see [README.md](README.md). `make help` lists every target.

## Workflow

1. Branch from `main`.
2. Make your change and **test it**: run the relevant `make` target or
   `scripts/setup-*.sh` and confirm the affected service is healthy (`docker ps`).
   Shared infra (Redis/Qdrant/observability) comes from a shared stack you provide on
   the external `shared` Docker network — start it first.
3. Open a pull request describing what changed and why.

## Conventions

- **Secrets never enter git.** Real values live in gitignored files (`config/.env`,
  `docker/searxng/settings.yml`); commit only the `*.example` templates. The setup scripts
  generate secrets on first run. Shared-infra credentials (Redis/Qdrant) belong to
  your shared stack.
- **Docs and comments follow the `documentation-minimalism` skill**
  (`.claude/skills/documentation-minimalism/SKILL.md`): explain intent, not
  mechanics; cut redundancy; keep operational content in markdown, not source.
- **Pin Docker images by digest** (`image: name:tag@sha256:...`).
- **Record durable changes:** update `.claude/MEMORY.md` for project knowledge.
- **Commits:** imperative subject, body explaining *why*.

[CLAUDE.md](CLAUDE.md) maps the repo and lists the invariants worth keeping.

## Reporting bugs

Open an issue with your macOS version, the failing command, and the relevant log
(`docker logs <container>` or `~/.hermes/logs/agent.log`). For security issues,
see [SECURITY.md](SECURITY.md).
