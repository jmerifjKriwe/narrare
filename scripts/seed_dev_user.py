#!/usr/bin/env python3
"""
Seed the development database with a pre-configured dev user.
Safe to run multiple times (idempotent).

Dev credentials:
  Email:    dev@narrare.dev
  Password: narrare-dev
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add workspace packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


async def seed() -> None:
    # Import here so path is set up first
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from narrare._app.config import get_settings
    from narrare.auth.models import User
    from narrare.auth.security import hash_password

    # Resolve the dev DB URL through the app Settings (pydantic-settings reads
    # the root .env via env_file). This keeps a custom DATABASE_URL from .env
    # authoritative even without just's dotenv-load; precedence mirrors the
    # previous os.environ.get: env var > .env file > dev default.
    database_url = get_settings().database_url

    engine = create_async_engine(database_url, echo=False, poolclass=NullPool)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session_maker() as session:
        # Check if dev user already exists
        result = await session.execute(
            select(User.id).where(User.email == "dev@narrare.dev").limit(1)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("✅ Dev user already exists (dev@narrare.dev)")
            await engine.dispose()
            return

        # Create dev user using ORM (applies Python-level uuid.uuid4 default)
        hashed = hash_password("narrare-dev")

        user = User(
            email="dev@narrare.dev",
            hashed_password=hashed,
            is_active=True,
            is_verified=True,
            display_name="Dev User",
        )
        session.add(user)
        await session.flush()  # Generates the UUID via Python default
        await session.commit()
        print("✅ Dev user created: dev@narrare.dev / narrare-dev")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
