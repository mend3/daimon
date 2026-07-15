# Architecture Decision Records

Major decisions that remain relevant. Newest first.

## ADR-0015 — Shared infra is consumed by DNS, never declared here

**Status:** Accepted

**Context:** Daimon was written for a single-machine macOS setup: Ollama installed natively
on the host (Metal GPU), reached from the devcontainer at `host.docker.internal:11434`,
with `make ollama` installing and pulling models. Deployed next to an existing infra stack
that already runs Ollama/Qdrant/Redis and an observability plane on its own Docker network,
that shape breaks twice over: the endpoint does not resolve, and Daimon would be installing
a second Ollama beside the one already running.

**Decision:** Everything shared is **external and consumed by DNS** on a Docker network the
operator owns — `SHARED_NETWORK` (default `shared`), joined by both the sidecars and the
devcontainer. Daimon reaches `ollama:11434`, `qdrant:6333`, `redis:6379`, `loki:3100` and
`grafana:3000` by name, and declares **none** of them in its compose. `host.docker.internal`
is gone from the config; only Daimon's own sidecars (searxng, tts) live here, aliased
`daimon-*` on the shared network so their generic names do not collide with other stacks.
`make ollama` is dropped: installing and tuning Ollama, pulling models and setting
`OLLAMA_CONTEXT_LENGTH` all belong to whoever runs the shared stack. `make doctor` probes
from *inside* the network (a throwaway container) rather than from the host, since that is
the vantage point the devcontainer actually has.

**Consequences:** Daimon no longer runs standalone — the shared stack must be up first, or
the network does not exist and nothing attaches. Metal-accelerated inference is no longer a
property of this repo; it depends on where the shared Ollama runs. The ≥64K context window
Hermes requires and the model pulls become **operator obligations**: `make doctor` reports
them as gaps instead of fixing them, because both settings affect every consumer of that
Ollama. Daimon's sidecars are reachable by anything else on the shared network — the
isolation boundary is the network, not a loopback port. The macOS-host scripts
(`setup-ollama-host.sh`, launchd, pfctl) are inert off macOS and kept only for that host.

## ADR-0014 — Default to OpenAI gpt-5-mini with a local Ollama fallback; model profiles

**Status:** Accepted

**Context:** The owner wanted OpenAI as the primary model for the agents, the local
model kept as a fallback, and their Claude subscription available on demand — without
losing the offline path. Hermes' `openai-api` provider (used for gpt-5.x) reads its
key/endpoint from the `OPENAI_API_KEY`/`OPENAI_BASE_URL` *environment*, not config,
and the container points those at the local Ollama.

**Decision:** Three model backends as profiles:
- **`default`** (base home) — OpenAI **gpt-5-mini** (`openai-api`, Responses API) with a
  `fallback_providers` entry for local **gpt-oss:20b** (fires on 429/5xx/401/404/empty,
  turn-scoped). postCreate writes the real `OPENAI_API_KEY`/`OPENAI_BASE_URL` into
  `~/.hermes/.env` from the single `OPENAI_PROFILE_API_KEY`, overriding the container's
  Ollama-pointing values (the profile `.env` loads with precedence).
- **`ollama`** — fully local `gpt-oss:20b` (offline, no API cost).
- **`claude-max`** — the Claude subscription (`anthropic`, `claude-sonnet-4-5`), OAuth
  from `CLAUDE_CODE_OAUTH_TOKEN`. Named `claude-max`, not `claude`, so its profile
  launcher doesn't clobber the Claude Code CLI binary.

Profiles are versioned under `config/profiles/` and synced by a generic postCreate
loop. The prior single-purpose `openai` task profile is removed (the default now is
OpenAI). Approvals stay `manual` everywhere — the kanban dispatcher runs tasks headless
and bypasses approvals itself, so no `off` profile is needed.

**Consequences:** The default now needs an OpenAI key and bills per call (the Telegram
gateway and unassigned kanban tasks included); the Ollama fallback keeps it answering
through outages, and the `ollama` profile stays a zero-cost offline option. Local-first
is no longer the default — Ollama remains the vision/embedding backend and the fallback.
`claude-max` requires a Max plan with **extra usage credits** (else HTTP 400 "out of
extra usage"); the base allowance is not usable via Hermes. Reasoning-model-only on the
default (encrypted reasoning content); a non-reasoning model would 400.

## ADR-0013 — Autonomous kanban: in-gateway dispatcher + OpenAI task profile

**Status:** Accepted

**Context:** The kanban board's dispatcher runs inside the gateway process, but
`start-gateway.sh` only started the gateway when a Telegram token was set — so a
Telegram-less setup had no dispatcher and `ready` tasks never spawned. Separately,
task agents should be able to run on the OpenAI API while interactive chat stays
local/offline.

**Decision:** Start the gateway (hence the dispatcher) **regardless of Telegram**;
the allowlist guard now fires only when a token *is* set. Task model selection rides
on **profiles** (the kanban assignee is a profile name): a versioned `openai` profile
(`config/profiles/openai/config.yaml`, synced to `~/.hermes/profiles/openai/`) runs on
the OpenAI API. Its `base_url`/`api_key` are set **explicitly** to override the
container-level `OPENAI_*` env that points at Ollama; the key resolves from
`OPENAI_PROFILE_API_KEY` in `~/.hermes/.env`, which `postCreate` propagates into the
profile's isolated `.env`. The profile runs `approvals: off` (headless tasks can't
answer prompts) with Tirith still fail-closed as the safety net.

**Consequences:** The gateway/dispatcher now always run; tasks must be in `ready`
**with an assignee** to spawn (an unassigned `ready` task is skipped). The default
profile stays fully local; only tasks assigned to `openai` reach the cloud. Other
per-purpose profiles follow the same pattern. The web dashboard needs Node (devcontainer
feature) + the `[web,pty]` extras, both wired into the container build.

## ADR-0011 — Headless workflow engine (typed node graph, not gRPC)

**Status:** Accepted

**Context:** Daimon needs a way to compose her capabilities into automations
(n8n-style) that runs unattended, defined in config/code rather than a UI. A gRPC node
mesh was considered.

**Decision:** A typed, headless **node-graph engine** (`ingestion/daimon_flow`) where
nodes are Daimon's capabilities and two port kinds keep graphs clean — solid **flow**
edges carry execution, dotted **resource** edges attach dependencies (model, knowledge,
tools) to the agent. Same Registry/Factory/Strategy/Observer patterns as `daimon_kb`;
new node types are a drop-in (in-tree or via a `daimon_flow.nodes` entry point).
Workflows are defined and run programmatically, with no server or UI. **gRPC was
deferred**: the components are local/in-process and already expose JSON Schemas, so a
typed JSON contract is lighter; gRPC stays an option only if nodes become distributed.

**Consequences:** The engine installs into the Hermes venv and reaches Ollama/Qdrant
like the rest of Daimon's code. The Telegram bot is unchanged.

## ADR-0010 — Local voice replies via an OpenAI-compatible TTS service

**Status:** Accepted (the `hermes-shared` network it names is now `SHARED_NETWORK`, see ADR-0015)

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

**Context:** Daimon needed a personal knowledge base that concentrates the user's
links, files, notes, and other sources, recalled by meaning — without the local
model doing vector math, and with new source types easy to add.

**Decision:** A Python package (`ingestion/daimon_kb`) with a deterministic core
(chunk, embed via Ollama `nomic-embed-text`, store, ledger, security) and pluggable
**source adapters** (Adapter + Factory/Registry + Template Method patterns). Each
**enabled source type is a capability with its own Qdrant collection**
(`kb_<type>__nomic768`); `files`/`urls`/`chat` ship on, `feeds` (Miniflux) and
`webhook` are example connectors off by default. A **SQLite ledger is the source of
truth**; Qdrant is a rebuildable index. Idempotent point IDs + content-hash dedup;
SSRF guard + secret redaction + score-thresholded fan-out retrieval. Exposed to Daimon
as a custom MCP server (`daimon-kb`: capture/recall/forget/list_recent) — not the
official `mcp-server-qdrant`, which only embeds via FastEmbed (a different vector
space) and lacks the payload/dedup/chunking we need.

**Consequences:** New host service (Qdrant, loopback + API key) and an embedding
model pull. Store and query must share the embedding model + nomic task prefixes.
Adding a source type is a zero-core-change adapter drop-in (in-tree or via an
`daimon_kb.adapters` entry point). Google Calendar/Sheets deferred.

## ADR-0008 — One shared Redis on the hermes-shared network

**Status:** Superseded by ADR-0015 — Redis is no longer Daimon's to run; it comes from the shared stack (db 5)

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

**Status:** Accepted (endpoints since moved to shared-network DNS, see ADR-0015)

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

**Status:** Superseded by ADR-0015 — Daimon no longer installs Ollama

**Context:** The Homebrew `ollama` CLI formula lacks the Metal runner and falls
back to CPU on Apple Silicon.

**Decision:** Install the `ollama-app` cask, which bundles the Metal runner.

**Consequences:** Confirm with `library=Metal` in the Ollama log.

## ADR-0002 — Ollama runs natively on the host, not in Docker

**Status:** Superseded by ADR-0015 — Ollama comes from the shared stack, reached at `ollama:11434`

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
