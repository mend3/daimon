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
- `~/.hermes/` (config, memories, sessions, skills, logs, installed agent code)
  persists in the named Docker volume **`hermes-data`** across rebuilds.
- `config/config.yaml` is the source of truth; `postCreate.sh` syncs it into
  `~/.hermes/config.yaml` and installs Hermes on container create.

# Technical Standards

- **Model:** `gpt-oss:20b` (MoE, ~3.6B active), served at a **64K context window**.
- **Ollama install:** official `ollama-app` Homebrew cask (Metal runner), bound to
  `0.0.0.0`, with `OLLAMA_CONTEXT_LENGTH=65536`, flash attention, `q8_0` KV cache.
- **Devcontainer:** Debian base; Hermes installed via the official installer into
  the persisted volume. `~/.local/bin` on PATH via Dockerfile `ENV`.
- Documentation follows the `documentation-minimalism` skill: intent over
  mechanics, no negative guidance, no code-restating comments.

# Integrations

- **Ollama** via its OpenAI-compatible `/v1` endpoint.
- **Web search** is disabled by default (no API keys). Backends available:
  searxng, firecrawl, tavily, exa.

# Known Constraints

- Hermes **requires a model with ≥64K context**. Models capping below that are
  rejected at startup (`qwen3:8b` maxes at 40,960 on Ollama and cannot extend
  without re-converting the GGUF with YaRN).
- Ollama must bind **`0.0.0.0`** (not `127.0.0.1`) for the container to reach it.
- Model must fit the host's ~17.8 GiB Metal VRAM budget to stay 100% on GPU.
- macOS-host-specific: Homebrew cask, `launchctl setenv`, `host.docker.internal`.

Major decisions are recorded in `DECISIONS.md`.
