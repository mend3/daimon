# Contributing

This repo is configuration, scripts, and docs for running Hermes Agent locally
(macOS host + devcontainer). There is no application code to build.

## Setup

You need macOS with Docker Desktop and Homebrew. `make up` brings up the host
services; see [README.md](README.md). `make help` lists every target.

## Workflow

1. Branch from `main`.
2. Make your change and **test it**: run the relevant `make` target or
   `scripts/setup-*.sh` and confirm the affected service is healthy
   (`docker ps`, `make monitoring` → http://localhost:3000).
3. Open a pull request describing what changed and why.

## Conventions

- **Secrets never enter git.** Real values live in gitignored files (`config/.env`,
  `redis/.env`, `monitoring/.env`, `searxng/settings.yml`, generated
  `contactpoints.yaml`); commit only the `*.example` templates. The setup scripts
  generate passwords/secrets on first run.
- **Docs and comments follow the `documentation-minimalism` skill**
  (`.claude/skills/documentation-minimalism/SKILL.md`): explain intent, not
  mechanics; cut redundancy; keep operational content in markdown, not source.
- **Pin Docker images by digest** (`image: name:tag@sha256:...`).
- **Record durable changes:** update `.claude/MEMORY.md` for project knowledge and
  add an ADR to `.claude/DECISIONS.md` for major decisions.
- **Commits:** imperative subject, body explaining *why*.

[CLAUDE.md](CLAUDE.md) maps the repo and lists the invariants worth keeping.

## Reporting bugs

Open an issue with your macOS version, the failing command, and the relevant log
(`docker logs <container>` or `~/.hermes/logs/agent.log`). For security issues,
see [SECURITY.md](SECURITY.md).
