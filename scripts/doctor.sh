#!/usr/bin/env bash
# Preflight: check the services and models Daimon depends on, before bringing him
# up. Run from the host as `make doctor`. Everything Daimon talks to lives on
# the shared network, so probe from a throwaway container on it rather than from the
# host — that is the vantage point Daimon's container actually has.
# Exits non-zero only on a core dependency: the network and Ollama itself. Which models
# are pulled is the operator's call, so a missing one degrades a path (fallback, vision,
# knowledge base) and warns — the OpenAI default profile answers without any of them.
set -uo pipefail

pass=0; warn=0; fail=0
PASS() { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass + 1)); }
WARN() { printf '  \033[33m!\033[0m %s\n' "$1"; warn=$((warn + 1)); }
FAIL() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail + 1)); }

NET="${SHARED_NETWORK:-shared}"
INFRA_HINT="start your shared infra stack on the '${NET}' network"
CURL_IMAGE="curlimages/curl:latest"

# Fetch a URL from inside the shared network, printing the body (empty on any failure).
fetch_net() { docker run --rm --network "$NET" "$CURL_IMAGE" -sS -m 6 "$1" 2>/dev/null || true; }
# A URL is "serving" if curl gets any HTTP response at all.
reach_net() { docker run --rm --network "$NET" "$CURL_IMAGE" -sS -o /dev/null -m 6 "$1" >/dev/null 2>&1; }

echo "Daimon preflight (from the '${NET}' network)"
echo

# --- The network itself: nothing below can pass without it -------------------
if ! docker network inspect "$NET" >/dev/null 2>&1; then
  FAIL "Docker network '${NET}' missing — ${INFRA_HINT}"
  echo
  printf 'Summary: %d ok, %d warnings, %d failures\n' "$pass" "$warn" "$fail"
  exit 1
fi
PASS "Docker network '${NET}' exists"

# --- Core: the shared Ollama + the models Daimon needs -----------------------
TAGS="$(fetch_net http://ollama:11434/api/tags)"
if [ -n "$TAGS" ]; then
  PASS "Ollama reachable (ollama:11434)"
  has_model() { printf '%s' "$TAGS" | grep -q "\"$1"; }
  MODEL_HINT="pull it on your shared Ollama"
  has_model "gpt-oss:20b"      && PASS "model gpt-oss:20b (fallback + 'ollama' profile)" || WARN "model gpt-oss:20b missing — no local fallback, 'ollama' profile unusable; ${MODEL_HINT}"
  has_model "qwen2.5vl:7b"     && PASS "model qwen2.5vl:7b (vision)"                     || WARN "model qwen2.5vl:7b missing — vision degraded; ${MODEL_HINT}"
  has_model "nomic-embed-text" && PASS "model nomic-embed-text (KB)"                     || WARN "model nomic-embed-text missing — knowledge base degraded; ${MODEL_HINT}"

  # Hermes rejects any local model served below a 64K window, so a too-small
  # OLLAMA_CONTEXT_LENGTH breaks the local paths at startup rather than here.
  echo "    note: local models need a ≥64K window (OLLAMA_CONTEXT_LENGTH) on that Ollama"
else
  FAIL "Ollama unreachable (ollama:11434) — ${INFRA_HINT}"
fi

# --- The other shared services Daimon consumes -------------------------------
reach_net "http://qdrant:6333/healthz" && PASS "Qdrant (qdrant:6333)" || WARN "Qdrant unreachable — ${INFRA_HINT}"
docker run --rm --network "$NET" redis:alpine redis-cli -h redis -p 6379 ping >/dev/null 2>&1 \
  && PASS "Redis (redis:6379, SearXNG uses db 5)" || WARN "Redis unreachable — ${INFRA_HINT}"

# --- Search and voice, provided by the shared stack --------------------------
# Declared by the shared stack (the oracle), not here — so this is a reachability check,
# not a local-file check. The generated settings.yml that used to be verified here moved
# there too, along with the service that bind-mounts it.
reach_net "http://searxng:8080/healthz" && PASS "SearXNG (web search)" || WARN "SearXNG down — start it in the shared stack (oracle: make up searxng)"
reach_net "http://tts:8880/health"      && PASS "TTS (voice)"          || WARN "TTS down — start it in the shared stack (oracle: make up nvidia speech)"

# --- The persona, served by the hub ------------------------------------------
# setup.sh fetches it on every start and falls back to config/SOUL.md, so nothing here
# is fatal — but a silent fallback means Daimon boots with a stale identity, which is
# exactly what this reports. Vars come from the environment or the repo .env, the same
# file compose reads.
ENV_FILE="$(dirname "${BASH_SOURCE[0]}")/../.env"
if [ -f "$ENV_FILE" ]; then
  HUB_INTERNAL_URL="${HUB_INTERNAL_URL:-$(sed -n 's/^HUB_INTERNAL_URL=//p' "$ENV_FILE" | head -1)}"
  HUB_WORKER_TOKEN="${HUB_WORKER_TOKEN:-$(sed -n 's/^HUB_WORKER_TOKEN=//p' "$ENV_FILE" | head -1)}"
fi
if [ -z "${HUB_INTERNAL_URL:-}" ] || [ -z "${HUB_WORKER_TOKEN:-}" ]; then
  WARN "HUB_INTERNAL_URL/HUB_WORKER_TOKEN unset — persona pinned to config/SOUL.md (may be stale)"
else
  PERSONA_CODE=$(docker run --rm --network "$NET" "$CURL_IMAGE" -sS -o /dev/null -w '%{http_code}' -m 6 \
    -H "x-internal-token: ${HUB_WORKER_TOKEN}" "${HUB_INTERNAL_URL%/}/api/internal/persona" 2>/dev/null || echo 000)
  case "$PERSONA_CODE" in
    200) PASS "Persona served by the hub (${HUB_INTERNAL_URL})" ;;
    401) WARN "Hub rejected HUB_WORKER_TOKEN (401) — it must match the hub's; booting on config/SOUL.md" ;;
    *)   WARN "Hub not serving the persona (HTTP ${PERSONA_CODE}) — booting on config/SOUL.md" ;;
  esac
fi

echo
printf 'Summary: %d ok, %d warnings, %d failures\n' "$pass" "$warn" "$fail"
[ "$fail" -eq 0 ]
