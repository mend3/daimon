# Image for the container Hermes runs in (CLI, isolated) — built by docker-compose.
# Debian Bookworm devcontainer base already ships git, curl, sudo and a
# passwordless "vscode" user. The Hermes installer brings its own uv / Python 3.11,
# so here we only add the native deps it expects to find on PATH, plus Node for the
# web dashboard frontend (the installer's bundled Node is not on PATH).
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
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Hermes installs its launcher to ~/.local/bin; make sure it is on PATH for
# every shell (login, non-login, and the entrypoint's setup step).
ENV PATH="/home/vscode/.local/bin:${PATH}"

USER vscode

# Compose bind-mounts the repo here. The entrypoint derives the repo root from its
# own location, so this path is the only place the layout is stated.
WORKDIR /workspace

ENTRYPOINT ["/workspace/docker/agent/entrypoint.sh"]
