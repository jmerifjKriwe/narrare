#!/usr/bin/env bash
set -euo pipefail

echo "Setting up the Narrare devcontainer..."

sudo chown -R vscode:vscode /workspace/.venv

sudo chown -R vscode:vscode /home/vscode/.opencode \
                            /home/vscode/.config/opencode \
                            /home/vscode/.local/state/opencode \
                            /home/vscode/.local/share/opencode \
                            /home/vscode/.cache/opencode

echo "Installing Python dependencies..."
uv sync

echo "Installing frontend dependencies..."
pnpm install

echo "Installing git hooks..."
uv run pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push

if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
fi

# Inside the container Postgres answers to the compose service name, not to
# localhost. This script only ever runs in the devcontainer lifecycle, so the
# rewrite does not need to guess where it is.
echo "Pointing the database URL at the compose service..."
sed -Ei 's|(NARRE_DATABASE_URL=postgresql\+asyncpg://[^:]+:[^@]+@)localhost:5432/|\1postgres:5432/|g' .env

echo "Waiting for the database..."
for _ in {1..30}; do
  if docker compose -f docker-compose.dev.yml exec -T postgres pg_isready -U narrare >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Running migrations..."
just db-migrate

echo
echo "Ready."
echo "  just dev        API on :8000, web on :3100"
echo "  just --list     every command"
echo

# Personal local additions (not tracked in git)
if [ -f ".devcontainer/post-create.local.sh" ]; then
    bash .devcontainer/post-create.local.sh
fi
