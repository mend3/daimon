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

# Path DISCOVERED, not hardcoded: the CLI mounts at /workspaces/<folder-name>, so a
# repo directory named anything but "hermes" pointed this at a file that does not
# exist. Combined with the silencing below, the gateway never started and the
# container stayed up, healthy and mute — with no error anywhere to find.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Errors are LOUD: `>/dev/null 2>&1 || true` hid both "file not found" and every
# gateway failure. A gateway problem still must not stop the container (the ||
# true stays), but it has to leave a trace in `docker logs`.
if ! bash "$here/start-gateway.sh"; then
  echo "[container-boot] gateway falhou ao subir — o container segue de pé, mas NÃO responde no Telegram" >&2
fi

exec sleep infinity
