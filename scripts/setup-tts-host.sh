#!/usr/bin/env bash
# Starts the local TTS engine (Kokoro-FastAPI, OpenAI-compatible) on the shared network
# and 127.0.0.1:8880.
#
# Daimon reaches it from the devcontainer at daimon-tts:8880; Hermes' `openai` TTS
# provider is pointed there in config/config.yaml. First start pulls the image and
# downloads the voice model into the tts-models volume (~minutes).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> Starting TTS (Kokoro-FastAPI)"
docker compose up -d tts

echo "==> Waiting for TTS (first run downloads the voice model)"
for _ in $(seq 1 60); do
  if [ "$(docker inspect -f '{{.State.Health.Status}}' hermes-tts 2>/dev/null)" = "healthy" ]; then
    echo "    OK - TTS healthy on daimon-tts:8880 (and 127.0.0.1:8880)"
    exit 0
  fi
  sleep 5
done

echo "    WARN - TTS not healthy in time. Check: docker logs hermes-tts"
exit 1
