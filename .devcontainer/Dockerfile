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
