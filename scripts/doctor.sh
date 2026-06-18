#!/usr/bin/env bash
# Preflight: check the host services and models Ella depends on, before opening the
# devcontainer. Run from the host as `make doctor`. Exits non-zero only if a core
# dependency (Ollama + the chat model) is missing; other gaps print as warnings.
set -uo pipefail

pass=0; warn=0; fail=0
PASS() { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass + 1)); }
WARN() { printf '  \033[33m!\033[0m %s\n' "$1"; warn=$((warn + 1)); }
FAIL() { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail + 1)); }

# A port is "serving" if curl gets any HTTP response (000 = no connection).
reach() {
  local code
  code=$(curl -sS -o /dev/null -m 4 -w '%{http_code}' "$1" 2>/dev/null || true)
  [ -n "$code" ] && [ "$code" != "000" ]
}
echo "Ella host preflight"
echo

# --- Core: Ollama + models ---------------------------------------------------
TAGS="$(curl -sS -m 4 http://localhost:11434/api/tags 2>/dev/null || true)"
if [ -n "$TAGS" ]; then
  PASS "Ollama reachable (localhost:11434)"
  has_model() { printf '%s' "$TAGS" | grep -q "\"$1"; }
  has_model "gpt-oss:20b"     && PASS "model gpt-oss:20b (chat)"        || FAIL "model gpt-oss:20b missing — run: make ollama"
  has_model "qwen2.5vl:7b"    && PASS "model qwen2.5vl:7b (vision)"     || WARN "model qwen2.5vl:7b missing — vision degraded"
  has_model "nomic-embed-text" && PASS "model nomic-embed-text (KB)"   || WARN "model nomic-embed-text missing — knowledge base degraded"
else
  FAIL "Ollama unreachable (localhost:11434) — run: make ollama (and OLLAMA_HOST=0.0.0.0)"
fi

# --- Ella host sidecars ------------------------------------------------------
reach "http://localhost:8888"          && PASS "SearXNG (web search, :8888)"        || WARN "SearXNG down (:8888) — run: make searxng"
reach "http://localhost:8880/health"   && PASS "TTS (voice, :8880)"                  || WARN "TTS down (:8880) — run: make tts"

# --- Shared infra (owned by oracle on the `workspace` network) ----------------
# redis/qdrant/observability come from oracle, not Ella. Probe the network and,
# best-effort, the services from a throwaway container on `workspace`.
ORACLE="cd ../oracle && make up"
if docker network inspect workspace >/dev/null 2>&1; then
  PASS "Docker network 'workspace' exists (oracle infra)"
  qprobe() { docker run --rm --network workspace curlimages/curl:latest -sS -o /dev/null -m 4 "$1" >/dev/null 2>&1; }
  qprobe "http://qdrant:6333/healthz"  && PASS "Qdrant (oracle, qdrant:6333)"  || WARN "Qdrant unreachable on workspace — run: ${ORACLE}"
  docker run --rm --network workspace redis:alpine redis-cli -h redis -p 6379 ping >/dev/null 2>&1 \
    && PASS "Redis (oracle, redis:6379/5)" || WARN "Redis unreachable on workspace — run: ${ORACLE}"
else
  WARN "Docker network 'workspace' missing — bring up oracle: ${ORACLE}"
fi

echo
printf 'Summary: %d ok, %d warnings, %d failures\n' "$pass" "$warn" "$fail"
[ "$fail" -eq 0 ]
