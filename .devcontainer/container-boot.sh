#!/usr/bin/env bash
# Container main process (devcontainer overrideCommand=false). Starts the
# messaging gateway as a child of PID 1 — so it survives, unlike a process
# spawned from a lifecycle hook — then idles to keep the container alive.
# Always ends in `sleep infinity`, so a gateway problem never stops the container.

# On a fresh volume, postCreate installs Hermes and syncs config in parallel; wait
# for both before starting the gateway. On later starts both already exist.
for _ in $(seq 1 150); do
  if command -v hermes >/dev/null 2>&1 && grep -q "gpt-oss" ~/.hermes/config.yaml 2>/dev/null; then
    break
  fi
  sleep 2
done

bash /workspaces/hermes/.devcontainer/start-gateway.sh >/dev/null 2>&1 || true

exec sleep infinity
