FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    jq \
    build-essential \
    libpq-dev \
    postgresql-client \
    # just (task runner)
    && curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
    | bash -s -- --to /usr/local/bin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN su vscode -c "curl -LsSf https://astral.sh/uv/install.sh | sh"
ENV PATH="/home/vscode/.cargo/bin:/home/vscode/.local/bin:$PATH"

# Install Node.js LTS (via nvm for flexibility)
ARG NODE_VERSION=24
RUN su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh \
    && nvm install ${NODE_VERSION} \
    && nvm alias default ${NODE_VERSION}" 2>&1

# Install pnpm
ARG PNPM_VERSION=10.24.0
RUN su vscode -c ". /usr/local/share/nvm/nvm.sh && npm install -g pnpm@${PNPM_VERSION}" 2>&1

# Install pre-commit
RUN pip install pre-commit --break-system-packages

WORKDIR /workspace

# Set environment variables for pnpm
ENV PNPM_HOME="/home/vscode/.local/share/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

# Correct permissions for vscode user
RUN mkdir -p /home/vscode/.vscode-server \
             /home/vscode/.cache \
             /home/vscode/.config/opencode \
             /home/vscode/.local/share/pnpm \
             /home/vscode/.opencode \
             /home/vscode/.local/state/opencode \
             /home/vscode/.local/share/opencode \
             /home/vscode/.cache/opencode \
    && chown -R vscode:vscode /home/vscode/
