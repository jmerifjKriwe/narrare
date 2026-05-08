#!/usr/bin/env python3
"""
Seed the development database with a pre-configured dev user.
Safe to run multiple times (idempotent).

Dev credentials:
  Email:    dev@narrare.local
  Password: narrare-dev
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add workspace packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


async def seed() -> None:
    # Import here so path is set up first
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_dev",
    )

    engine = create_async_engine(database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session_maker() as session:
        # Check if dev user already exists
        result = await session.execute(
            text("SELECT id FROM users WHERE email = 'dev@narrare.local' LIMIT 1")
        )
        existing = result.fetchone()

        if existing:
            print("✅ Dev user already exists (dev@narrare.local)")
            await engine.dispose()
            return

        # Create dev user
        # Note: In production code this uses auth/service.py
        # Here we insert directly for bootstrap purposes
        import bcrypt

        hashed = bcrypt.hashpw(b"narrare-dev", bcrypt.gensalt()).decode()

        await session.execute(
            text("""
                INSERT INTO users (email, hashed_password, is_active, is_verified, display_name)
                VALUES ('dev@narrare.local', :pwd, true, true, 'Dev User')
            """),
            {"pwd": hashed},
        )
        await session.commit()
        print("✅ Dev user created: dev@narrare.local / narrare-dev")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
