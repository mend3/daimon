# Ella

[![lint](https://github.com/mend3/ella/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/mend3/ella/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Platform: macOS](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-black?logo=apple&logoColor=white)
![local LLM: Ollama](https://img.shields.io/badge/local%20LLM-Ollama%20gpt--oss-5A67D8)
![Devcontainer](https://img.shields.io/badge/devcontainer-Docker-2496ED?logo=docker&logoColor=white)
![Built on: Hermes Agent](https://img.shields.io/badge/built%20on-Hermes%20Agent-6E56CF)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> An intelligent companion that helps you think, decide, create, and execute —
> yours to run, on your machine, and private when you want it.

**Ella** is a personal AI companion built on [Hermes
Agent](https://hermes-agent.nousresearch.com/docs/), sandboxed in a devcontainer on
your own machine. She defaults to **OpenAI gpt-5-mini** for quality, with a
**fully-local profile** and automatic fallback on [Ollama](https://ollama.com)
(Apple Silicon GPU) — so you can trade quality for privacy whenever you choose. She
combines human-like conversation with operational intelligence, reachable over CLI
and Telegram, and fully observable.

This repository is the **persona, deployment, multi-channel access, knowledge base,
visual workflows, and observability** built around Hermes. It is not
a fork of Hermes Agent — it stands on it (see [Built on](#built-on)).

## Meet Ella

Ella is not a chatbot. She is warm and genuinely human in conversation, precise and
operationally sharp in execution.

She is a thinking partner, researcher, operator, and advisor at once. Her defining
trait is **anticipation** — she surfaces the risks, decisions, and opportunities you
haven't asked about yet. The feeling after talking to her should be:

> "She thought about things I hadn't considered yet."

Warm without being needy, efficient without being cold. Her full personality lives
in [`config/SOUL.md`](config/SOUL.md).

## Why Ella?

Most AI assistants are stateless chat windows. Ella is a persistent **companion**:

- 🧠 Keeps **long-term memory** across sessions and projects
- 🔭 **Anticipates** — risks, missing context, next decisions
- 🔍 **Searches the web** through a private, self-hosted engine
- 👁️ **Sees images** and 🎙️ **hears and speaks** voice
- 🛠️ **Executes tools** — shell, files, code, browser, web
- 🧩 **Builds workflows** on a visual canvas where the nodes are her own capabilities
- 💬 Reaches you over **CLI, Telegram, and a web canvas**, sharing one memory
- 📊 Is **fully observable** — every message, tool call, and model run on a dashboard
- 🔒 **Can run 100% locally** — a fully-local model profile + self-hosted services

## Core capabilities

### 🧠 Persistent memory
Ella builds context across conversations and projects — preferences, decisions,
documentation, history — instead of starting from zero each session.

### 🎨 Multimodal
Send text, **images** (analyzed by a local vision model), **voice** (transcribed
locally; she can reply in voice too), **links** (fetched and summarized), and
**files** (read and used). She works with all of them and tells you what she received.

### 🧩 Visual workflows
A web canvas to compose Ella's capabilities into automations — triggers, the agent,
tools, logic, and outputs as nodes, wired and run with live state. Nodes are her own
abilities; new node types drop in.

### 🛠️ Tool use
A modular toolset lets her act: web search, vision, file operations, code execution,
terminal, and browser automation — extensible with more.

### 🌐 Local-capable
The default model is OpenAI gpt-5-mini, but a **fully-local profile** (gpt-oss,
Qwen-VL via Ollama with Metal GPU) and an automatic local fallback are built in, and
search, cache, and monitoring are self-hosted (cache/vector store/observability via
the shared **oracle** infra) — so you can run with no cloud at all.

### 📨 Multi-channel
Talk to Ella from the **CLI**, **Telegram** (multi-user, allowlisted), or the **web
canvas**. The same memory and context follow you across every interface.

### 📊 Observability
A built-in Grafana + Loki + Prometheus stack gives live visibility into conversations
(per user), tool usage, model activity, and service health — with an "agent down"
alert straight to Telegram.

## Architecture

```text
                      ┌───────────────┐
       CLI / Web ────►      Ella       ◄────── Telegram
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
   Ella host sidecars:  Ollama (vision/embeddings) · SearXNG · TTS
   Shared infra (oracle, `workspace` network):  Redis · Qdrant · Miniflux · observability
```

Components are modular — they evolve independently. Shared infra (Redis, Qdrant,
and the Grafana/Loki/Prometheus observability plane) is provided centrally by the
**oracle** orchestrator on the `workspace` Docker network, not by Ella. Full
topology in [docs/setup.md](docs/setup.md).

## Built for privacy

> Your intelligence stack should belong to you.

Ella runs entirely on your own infrastructure with open models and self-hosted
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

macOS host with Docker Desktop + Homebrew:

```bash
git clone https://github.com/mend3/ella.git
cd ella
cd ../oracle && make up   # shared infra: workspace network + Redis/Qdrant/observability
cd ../ella && make up     # Ella's host sidecars: SearXNG + TTS (Ollama via `make ollama`)

unset NODE_OPTIONS VSCODE_INSPECTOR_OPTIONS
```

Then open the folder in a Dev Container ("Reopen in Container") and start talking to
Ella. Inside the container, `hermes` starts the agent and `hermes dashboard --port 8090`
opens the web dashboard (kanban, sessions, config); its frontend builds on first launch.
`make help` lists every target. Full installation and operations:
**[docs/setup.md](docs/setup.md)**.

## Built on

Ella stands on the shoulders of excellent open projects — she does not replace or
reproduce them:

- **[Hermes Agent](https://hermes-agent.nousresearch.com/docs/)** (Nous Research) — the agent framework and toolset.
- **[Ollama](https://ollama.com)** — local model serving with Metal GPU acceleration.
- **SearXNG** (search) runs as an Ella host sidecar; **Redis** (cache), **Qdrant**
  (vectors), and **Grafana / Loki / Prometheus** (observability) are provided by the
  shared **oracle** infra on the `workspace` network.

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
