#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Setting up Narrare development environment..."

sudo chown -R vscode:vscode /workspace/.venv

sudo chown -R vscode:vscode /home/vscode/.opencode \
                            /home/vscode/.config/opencode \
                            /home/vscode/.local/state/opencode \
                            /home/vscode/.local/share/opencode \
                            /home/vscode/.cache/opencode

# --- Python dependencies via uv ---
echo "📦 Installing Python dependencies..."
uv sync --all-packages --group dev

# --- Pre-commit hooks ---
echo "🔧 Installing pre-commit hooks..."
uv run pre-commit install --install-hooks

# --- Copy .env if not exists ---
if [ ! -f .env ]; then
  echo "📋 Creating .env from .env.example..."
  cp .env.example .env
  echo "  ⚠️  Edit .env and add your API keys before starting the API."
fi

# --- Adjust hostnames for dev container network ---
# Inside the dev container, services are reachable via docker service names
# (postgres, redis) not localhost. Detect by checking if docker CLI is absent.
if ! command -v docker >/dev/null 2>&1; then
  echo "🔧 Adjusting .env for dev container network..."
  sed -i 's|://narrare@localhost:5432|://narrare@postgres:5432|g' .env
  sed -i 's|://narrare@localhost:5433|://narrare@postgres_test:5432|g' .env
  sed -i 's|redis://localhost:6379|redis://redis:6379|g' .env
fi

# --- Frontend dependencies ---
echo "📦 Installing frontend dependencies..."
pnpm install

# --- Wait for DB and run migrations ---
echo "⏳ Waiting for database..."
for i in {1..30}; do
  if uv run python -c "
import asyncio, asyncpg, os
async def check():
    url = os.environ.get('DATABASE_URL', '').replace('+asyncpg', '')
    await asyncpg.connect(url)
asyncio.run(check())
" 2>/dev/null; then
    break
  fi
  sleep 2
done

echo "🗄️  Running database migrations..."
(cd apps/api && uv run alembic upgrade head)

echo "🌱 Seeding dev user..."
uv run python scripts/seed_dev_user.py

echo ""
echo "✅ Dev environment ready!"
echo ""
echo "Available commands:"
echo "  just dev          → Start all services"
echo "  just dev-api      → Start API only (port 8000)"
echo "  just dev-frontend → Start frontend only (port 3000)"
echo "  just test         → Run all tests"
echo "  just check        → Run all checks"
echo "  just --list       → Show all commands"
echo ""

# Personal local additions (not tracked in git)
if [ -f ".devcontainer/post-create.local.sh" ]; then
    bash .devcontainer/post-create.local.sh
fi
