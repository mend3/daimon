# Architecture Decision Records

Major decisions that remain relevant. Newest first.

## ADR-0012 — Plug-and-play web modules; Knowledge 3D graph

**Status:** Accepted

**Context:** The web app needed to grow beyond Workflows into separate features that
can be enabled/disabled (future: per plan tier / user). The first new one visualizes
the knowledge base.

**Decision:** The web frontend is a **module shell**: `GET /api/modules` returns the
enabled modules (from `ELLA_MODULES`, default `workflows,knowledge`; future
per-tier/user), and a left rail switches between them while the Chat panel stays
persistent. Each module is a self-contained React component registered by id. The
**Knowledge** module renders a 3D force graph (`react-force-graph-3d`) from
`GET /api/knowledge/graph`: a node per source (colored by type), edges to each
source's nearest semantic neighbours via Qdrant — including cross-type links (a url
relating to a feed item), drawn distinctly. The representative vector per source is
its first chunk's vector.

**Consequences:** New modules are a drop-in (a component + a registry entry + the
`ELLA_MODULES` gate); tier/user gating slots into `/api/modules` later. The graph is
built on demand (capped node count); large KBs may need precomputation/caching.

## ADR-0011 — Web canvas + workflow engine (typed node graph, not gRPC)

**Status:** Accepted

**Context:** Ella needed a browser/mobile experience beyond Telegram, and a way for
the user to compose her capabilities into automations (n8n-style). A gRPC node mesh
was considered.

**Decision:** A typed **node-graph engine** (`ingestion/ella_flow`) where nodes are
Ella's capabilities and two port kinds keep the canvas clean — solid **flow** edges
carry execution, dotted **resource** edges attach dependencies (model, knowledge,
tools) to the agent. Same Registry/Factory/Strategy/Observer patterns as `ella_kb`;
new node types are a drop-in (in-tree or via an `ella_flow.nodes` entry point). A
FastAPI backend (`ingestion/ella_web`, `ella-web` on :8099) serves the node catalog,
workflow CRUD, run (REST + WebSocket live states), executions, and a knowledge-
grounded chat. The frontend (`web/frontend`) is React + React Flow. **gRPC was
deferred**: the components are local/in-process and already expose JSON Schemas, so a
typed JSON contract is lighter; gRPC stays an option only if nodes become distributed.

**Consequences:** A web toolchain (Node/Vite) enters the repo. The backend installs
into the Hermes venv (`postCreate` extras `[mcp,feeds,web]`) and reaches Ollama/Qdrant
like the rest. Run `ella-web` + the Vite dev server, or build once and serve together
via `ELLA_WEB_STATIC`. The Telegram bot is unchanged.

## ADR-0010 — Local voice replies via an OpenAI-compatible TTS service

**Status:** Accepted

**Context:** Hermes supports TTS but defaults to the `edge` provider, which sends
reply text to Microsoft — at odds with the local-first posture. Voice-out was unset.

**Decision:** Run a local TTS engine (Kokoro-FastAPI, OpenAI-compatible) as a host
container (`tts/`, loopback, `hermes-shared`) and point Hermes' `openai` TTS provider
at it via `base_url`. Voice replies stay on the device.

**Consequences:** Another small host service (CPU; Docker on macOS has no Metal) and
a first-run model download. `NeuTTS` (Hermes' built-in local engine) is the fallback
if a separate service is unwanted.

## ADR-0009 — RAG knowledge base: Qdrant, pluggable adapters, ledger as truth

**Status:** Accepted

**Context:** Ella needed a personal knowledge base that concentrates the user's
links, files, notes, and other sources, recalled by meaning — without the local
model doing vector math, and with new source types easy to add.

**Decision:** A Python package (`ingestion/ella_kb`) with a deterministic core
(chunk, embed via Ollama `nomic-embed-text`, store, ledger, security) and pluggable
**source adapters** (Adapter + Factory/Registry + Template Method patterns). Each
**enabled source type is a capability with its own Qdrant collection**
(`kb_<type>__nomic768`); `files`/`urls`/`chat` ship on, `feeds` (Miniflux) and
`webhook` are example connectors off by default. A **SQLite ledger is the source of
truth**; Qdrant is a rebuildable index. Idempotent point IDs + content-hash dedup;
SSRF guard + secret redaction + score-thresholded fan-out retrieval. Exposed to Ella
as a custom MCP server (`ella-kb`: capture/recall/forget/list_recent) — not the
official `mcp-server-qdrant`, which only embeds via FastEmbed (a different vector
space) and lacks the payload/dedup/chunking we need.

**Consequences:** New host service (Qdrant, loopback + API key) and an embedding
model pull. Store and query must share the embedding model + nomic task prefixes.
Adding a source type is a zero-core-change adapter drop-in (in-tree or via an
`ella_kb.adapters` entry point). Google Calendar/Sheets deferred.

## ADR-0008 — One shared Redis on the hermes-shared network

**Status:** Accepted

**Context:** SearXNG ran its own Valkey purely for cache/limiter, and there was no
reusable cache for other containers.

**Decision:** Run a single password-protected Redis (`redis/`) on the external
`hermes-shared` Docker network. SearXNG uses db 1 over that network; db 0 is free
for current/future containers. Valkey was removed.

**Consequences:** One backend to run and secure; containers join `hermes-shared`
and connect to `redis:6379`. Redis must start before SearXNG. It binds loopback
only, so the devcontainer would join `hermes-shared` rather than use
host.docker.internal.

## ADR-0007 — Observability stack and security hardening

**Status:** Accepted

**Context:** A benchmark/audit found the agent/Ollama were log-only with no
alerting, and several hardening gaps (LAN-exposed services, Grafana anon-admin,
docker.sock mount, Tirith fail-open).

**Decision:** Add Prometheus + blackbox probing with an "Ollama down" Telegram
alert; bind Grafana to loopback; drop the Promtail docker.sock mount; set Tirith
fail-closed; pin images; tune Ollama (`NUM_PARALLEL=1`, `MAX_LOADED_MODELS=1`,
`KEEP_ALIVE=-1`). Persistence (launchd services) and the LAN firewall are scripts
the user runs explicitly.

**Consequences:** Real up/down alerting and a hardened default. Ollama/SearXNG
still bind `0.0.0.0` (required for container access); LAN risk is mitigated by an
opt-in firewall, not by loopback. GPU/VRAM metrics remain unavailable on macOS.

## ADR-0006 — Persist ~/.local and run the gateway under PID 1

**Status:** Accepted

**Context:** Every container rebuild reinstalled Hermes (~2 min) because the
uv-managed Python and launcher lived in container-only `~/.local`. Separately, the
messaging gateway could not be kept alive from a lifecycle hook — the tooling kills
processes spawned by `postStartCommand`, even with `setsid`.

**Decision:** Add a **`hermes-local`** volume for `~/.local`, so the toolchain
persists and rebuilds skip the install. Set `overrideCommand: false` and make the
container command `container-boot.sh` (PID 1) start the gateway and then idle.

**Consequences:** Rebuilds are ~2s instead of ~2min. The gateway auto-starts on
every container start and survives because it is a child of PID 1. `postStartCommand`
is not used. First-ever install on an empty volume still runs the full installer.

## ADR-0005 — Local-only integrations (vision, web search)

**Status:** Accepted

**Context:** The primary model `gpt-oss:20b` is text-only, and web search defaulted
to no backend. Both gaps should close without external API keys.

**Decision:** Add a dedicated vision model (`qwen2.5vl:7b`) on the same Ollama host
for the `vision` toolset, and run a local **SearXNG** for the `web` toolset.

**Consequences:** No third-party keys or data egress for vision or search. Ollama
may swap between the chat and vision models when VRAM is tight. SearXNG runs as a
host container reachable at `host.docker.internal:8888`.

## ADR-0004 — Default model: gpt-oss:20b

**Status:** Accepted

**Context:** Hermes requires a model with ≥64K context. The initial choice,
qwen3:8b, caps at 40,960 tokens on Ollama and cannot extend without re-converting
the GGUF with YaRN.

**Decision:** Use `gpt-oss:20b` — 128K native context, MoE (~3.6B active), fits the
host's ~17.8 GiB Metal VRAM at 100% GPU, strong tool calling.

**Consequences:** Served at a 64K window. If swapping, pick a model with ≥64K
native context: `llama3.1:8b`, `mistral-nemo:12b`, or `qwen3-coder:30b` (the last
exceeds VRAM and offloads partially to CPU).

## ADR-0003 — Ollama installed via the `ollama-app` cask

**Status:** Accepted

**Context:** The Homebrew `ollama` CLI formula lacks the Metal runner and falls
back to CPU on Apple Silicon.

**Decision:** Install the `ollama-app` cask, which bundles the Metal runner.

**Consequences:** Confirm with `library=Metal` in the Ollama log.

## ADR-0002 — Ollama runs natively on the host, not in Docker

**Status:** Accepted

**Context:** Docker on macOS has no Metal access; a containerized Ollama is
CPU-only.

**Decision:** Run Ollama natively on the host, bound to `0.0.0.0`; the container
connects via `host.docker.internal`.

**Consequences:** Hermes stays sandboxed in the container while inference stays
GPU-accelerated.

## ADR-0001 — Hermes isolated in a devcontainer

**Status:** Accepted

**Context:** Keep the agent and its tool execution off the host filesystem.

**Decision:** Run Hermes in a devcontainer with terminal backend `local` (the
container is the sandbox). Persist `~/.hermes` in the named volume `hermes-data`.

**Consequences:** Rebuilds preserve config, memories, and sessions; reset with
`docker volume rm hermes-data`.
