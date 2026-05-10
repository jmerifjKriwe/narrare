#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Setting up Narrare development environment..."

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

# --- Frontend dependencies ---
if [ -f packages/web/package.json ]; then
  echo "📦 Installing frontend dependencies..."
  cd packages/web && pnpm install && cd ../..
fi

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
