# Devcontainer base for Hermes Agent (CLI, isolated).
# Debian Bookworm devcontainer base already ships git, curl, sudo and a
# passwordless "vscode" user. The Hermes installer brings its own uv / Python 3.11
# / Node 22, so here we only add the native deps it expects to find on PATH.
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
# gateway under PID 1 and keep the container alive. Falls back to a plain idle if
# the boot script is missing, so the container always stays up.
CMD ["/bin/bash", "-c", "f=/workspaces/hermes/.devcontainer/container-boot.sh; if [ -f \"$f\" ]; then exec bash \"$f\"; else exec sleep infinity; fi"]
