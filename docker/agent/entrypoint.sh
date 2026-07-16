#!/usr/bin/env bash
# Container main process (PID 1). Provisions the persisted volumes and installs
# Hermes, then starts the messaging gateway as a child of PID 1 — so it survives,
# unlike a process spawned from a lifecycle hook — then idles to keep the container
# alive. Always ends in `sleep infinity`, so a setup or gateway problem never stops
# the container: `docker logs` stays reachable to say what went wrong.

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Setup runs to completion before the gateway starts — no waiting for a lifecycle
# hook racing in parallel. Idempotent: seconds on a warm volume, a full Hermes
# install on a fresh one.
if ! bash "$here/setup.sh"; then
  echo "[entrypoint] setup falhou — o container segue de pé para diagnóstico, mas o gateway NÃO sobe" >&2
  exec sleep infinity
fi

# Errors are LOUD: a gateway problem must not stop the container, but it has to
# leave a trace in `docker logs` instead of a container that is up, healthy and mute.
if ! bash "$here/start-gateway.sh"; then
  echo "[entrypoint] gateway falhou ao subir — o container segue de pé, mas NÃO responde no Telegram" >&2
fi

exec sleep infinity
