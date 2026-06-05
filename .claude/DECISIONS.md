# Architecture Decision Records

Major decisions that remain relevant. Newest first.

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
