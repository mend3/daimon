# Devcontainer base for Hermes Agent (CLI, isolated).
# Debian Bookworm devcontainer base already ships git, curl, sudo and a
# passwordless "vscode" user. The Hermes installer brings its own uv / Python 3.11,
# so here we only add the native deps it expects to find on PATH. Node (for the web
# dashboard frontend) comes from the node devcontainer feature, not the installer.
FROM mcr.microsoft.com/devcontainers/base:bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        ripgrep \
        ffmpeg \
        build-essential \
        less \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Hermes installs its launcher to ~/.local/bin; make sure it is on PATH for
# every shell (login, non-login, and the devcontainer's postCreate step).
ENV PATH="/home/vscode/.local/bin:${PATH}"

USER vscode

# Container main process (with devcontainer overrideCommand=false): start the
# gateway under PID 1 and keep the container alive.
#
# The workspace path is DISCOVERED, not hardcoded: the devcontainer CLI mounts at
# /workspaces/<folder-name>, so a repo directory named anything other than
# "hermes" silently fell through to `sleep infinity` — a container that is up,
# healthy and does nothing, with the gateway never starting and no error anywhere.
CMD ["/bin/bash", "-c", "f=$(ls -d /workspaces/*/.devcontainer/container-boot.sh 2>/dev/null | head -1); if [ -n \"$f\" ]; then exec bash \"$f\"; else echo 'container-boot.sh not found under /workspaces/*/.devcontainer — gateway NOT started' >&2; exec sleep infinity; fi"]
