# Daimon

[![lint](https://github.com/mend3/daimon/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/mend3/daimon/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Platform: macOS](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-black?logo=apple&logoColor=white)
![local LLM: Ollama](https://img.shields.io/badge/local%20LLM-Ollama%20gpt--oss-5A67D8)
![Docker](https://img.shields.io/badge/runs%20on-Docker%20Compose-2496ED?logo=docker&logoColor=white)
![Built on: Hermes Agent](https://img.shields.io/badge/built%20on-Hermes%20Agent-6E56CF)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> An intelligent companion that helps you think, decide, create, and execute —
> yours to run, on your machine, and private when you want it.

**Daimon** is a personal AI companion built on [Hermes
Agent](https://hermes-agent.nousresearch.com/docs/), sandboxed in a container on your
own machine. It runs **fully local** on [Ollama](https://ollama.com) (`gpt-oss:20b`),
owing nothing to anyone. It combines human-like conversation with operational
intelligence, reachable over CLI and Telegram, and fully observable.

This repository is the **persona, deployment, multi-channel access, knowledge base,
headless workflows, and observability** built around Hermes. It is not
a fork of Hermes Agent — it stands on it (see [Built on](#built-on)).

## Meet Daimon

Daimon is not a chatbot. It is warm and genuinely human in conversation, precise and
operationally sharp in execution.

It is a thinking partner, researcher, operator, and advisor at once. His defining
trait is **anticipation** — it surfaces the risks, decisions, and opportunities you
haven't asked about yet. The feeling after talking to him should be:

> "It thought about things I hadn't considered yet."

Warm without being needy, efficient without being cold. His full personality lives
in [`config/SOUL.md`](config/SOUL.md).

## Why Daimon?

Most AI assistants are stateless chat windows. Daimon is a persistent **companion**:

- 🧠 Keeps **long-term memory** across sessions and projects
- 🔭 **Anticipates** — risks, missing context, next decisions
- 🔍 **Searches the web** through a private, self-hosted engine
- 👁️ **Sees images** and 🎙️ **hears and speaks** voice
- 🛠️ **Executes tools** — shell, files, code, browser, web
- 🧩 **Runs workflows** that chain his own capabilities as nodes, defined in config
- 💬 Reaches you over **CLI and Telegram**, sharing one memory
- 📊 Is **fully observable** — every message, tool call, and model run on a dashboard
- 🔒 **Can run 100% locally** — a fully-local model profile + self-hosted services

## Core capabilities

### 🧠 Persistent memory
Daimon builds context across conversations and projects — preferences, decisions,
documentation, history — instead of starting from zero each session.

### 🎨 Multimodal
Send text, **images** (analyzed by a local vision model), **voice** (transcribed
locally; it can reply in voice too), **links** (fetched and summarized), and
**files** (read and used). It works with all of them and tells you what it received.

### 🧩 Workflows
A headless node-graph engine composes Daimon's capabilities into automations —
triggers, the agent, tools, logic, and outputs as nodes, defined in config and run
with live state. Nodes are his own abilities; new node types drop in.

### 🛠️ Tool use
A modular toolset lets him act: web search, vision, file operations, code execution,
terminal, and browser automation — extensible with more.

### 🌐 Local by default
The default model is **gpt-oss:20b** on your own Ollama (Qwen-VL for vision), and
search, cache, and monitoring are self-hosted (models/cache/vector store/observability
via a shared infra stack you provide) — so the out-of-the-box setup touches no cloud at
all. A `claude-max` profile rides your Claude subscription when you want frontier
quality.

### 📨 Multi-channel
Talk to Daimon from the **CLI** or **Telegram** (multi-user, allowlisted). The same
memory and context follow you across every interface.

### 📊 Observability
A built-in Grafana + Loki + Prometheus stack gives live visibility into conversations
(per user), tool usage, model activity, and service health — with an "agent down"
alert straight to Telegram.

## Architecture

```text
                      ┌───────────────┐
          CLI ────►      Daimon       ◄────── Telegram
                      │  (persona on   │
                      │  Hermes Agent) │
                      └───────┬───────┘
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐
   │   Memory    │    │    Tools     │    │   Intelligence   │
   │ sessions /  │    │ web · vision │    │ local LLMs       │
   │ state.db /  │    │ files · code │    │ (Ollama, Metal): │
   │ knowledge   │    │ browser      │    │ reasoning · plan │
   └─────────────┘    └──────────────┘    └──────────────────┘
          └───────────────────┬───────────────────┘
                              ▼
   Shared infra (your stack, shared network):  Ollama · Redis · Qdrant · observability
```

Components are modular — they evolve independently. Shared infra (Ollama, Redis,
Qdrant, and the Grafana/Loki/Prometheus observability plane) is provided by a stack
you run on an external Docker network — `SHARED_NETWORK`, default `shared` — and
consumed by DNS, not declared by Daimon. Full topology in
[docs/setup.md](docs/setup.md).

## Built for privacy

> Your intelligence stack should belong to you.

Daimon runs entirely on your own infrastructure with open models and self-hosted
services. The agent is sandboxed in a container, services are firewalled to the host,
and secrets never leave it — enabling data ownership, offline capability, no
per-token cloud costs, and independence from any single vendor.

## Use cases

- **Personal AI operating system** — a companion that knows your projects, files, and workflows.
- **Engineering companion** — research, debugging, architecture reviews, and documentation with context.
- **Knowledge management** — a searchable, living memory layer around your work.
- **Operations assistant** — monitor systems, receive alerts, investigate incidents, automate chores.
- **Research partner** — gather, synthesize, and retain findings over time.

## Getting started

A Docker host, plus a shared infra stack (Ollama, Redis, Qdrant + observability) running
on an external Docker network:

```bash
git clone https://github.com/mend3/daimon.git
cd daimon
export SHARED_NETWORK=shared  # the network your infra stack runs on
make doctor                   # what's reachable, what's missing
make up                       # Daimon (search and voice come from the shared stack)
```

That is it — the gateway starts with his container, so Telegram works with no terminal
open. `docker compose exec agent hermes` starts a CLI chat, and `hermes dashboard --port
8090` (from inside) opens the web dashboard on `localhost:8090` (kanban, sessions,
config); its frontend builds on first launch. To hack on Daimon himself, the repo ships
a dev container (`make devcontainer`). `make help` lists every target. Full installation
and operations: **[docs/setup.md](docs/setup.md)**.

## Built on

Daimon stands on the shoulders of excellent open projects — it does not replace or
reproduce them:

- **[Hermes Agent](https://hermes-agent.nousresearch.com/docs/)** (Nous Research) — the agent framework and toolset.
- **[Ollama](https://ollama.com)** — local model serving (chat, vision).
- **SearXNG** (search) and **TTS** (voice) run in the shared stack; **Ollama** (models), **Redis** (cache),
  **Qdrant** (vectors), and **Grafana / Loki / Prometheus** (observability) come from a
  shared stack you run on the shared network.

This repo adds the persona, the deployment, multi-channel access, and
the monitoring layer on top.

## Roadmap

- Knowledge-graph–backed memory
- Multi-agent collaboration; scheduled/triggered workflow runs
- Expanded tool ecosystem, workflow nodes, and custom integrations
- Cross-platform host support (beyond macOS)

## Contributing

Contributions, ideas, and feedback are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE). Covers this repository's persona, configuration, scripts, and docs —
Hermes Agent, Ollama, and the other software it builds on keep their own licenses.
