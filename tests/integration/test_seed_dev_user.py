"""Integration test for scripts/seed_dev_user.py.

Verifies the seeding function creates the dev user with correct credentials
and that the user can authenticate.
"""

from __future__ import annotations

from sqlalchemy import select

from narrare.auth.models import User
from narrare.auth.security import verify_password


class TestSeedDevUser:
    async def test_seed_creates_dev_user_with_correct_email(self, db_session) -> None:
        """Run seed function and verify dev user exists."""
        # Import here so test env is set up first
        from scripts.seed_dev_user import seed

        await seed()

        result = await db_session.execute(
            select(User).where(User.email == "dev@narrare.local").limit(1)
        )
        user = result.scalar_one_or_none()

        assert user is not None, "Dev user should exist after seeding"
        assert user.email == "dev@narrare.local"
        assert user.is_active is True
        assert user.is_verified is True
        assert user.display_name == "Dev User"

    async def test_seed_dev_user_password_verifies(self, db_session) -> None:
        """Verify the dev user's password can be verified."""
        from scripts.seed_dev_user import seed

        await seed()

        result = await db_session.execute(
            select(User).where(User.email == "dev@narrare.local").limit(1)
        )
        user = result.scalar_one_or_none()
        assert user is not None

        # Password should verify against the known dev password
        assert verify_password("narrare-dev", user.hashed_password) is True

    async def test_seed_dev_user_wrong_password_fails(self, db_session) -> None:
        """Verify that a wrong password does NOT verify."""
        from scripts.seed_dev_user import seed

        await seed()

        result = await db_session.execute(
            select(User).where(User.email == "dev@narrare.local").limit(1)
        )
        user = result.scalar_one_or_none()
        assert user is not None

        assert verify_password("wrong-password", user.hashed_password) is False

    async def test_seed_is_idempotent(self, db_session) -> None:
        """Running seed twice does not create duplicate users."""
        from scripts.seed_dev_user import seed

        await seed()
        await seed()  # Run again

        result = await db_session.execute(select(User).where(User.email == "dev@narrare.local"))
        users = result.scalars().all()

        assert len(users) == 1, "Seed should be idempotent — only one dev user"
