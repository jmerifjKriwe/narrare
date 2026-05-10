"""Auth repository — DB queries only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare.auth.models import User

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class AuthRepository:
    """DB queries for the auth domain."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        hashed_password: str,
        display_name: str = "",
    ) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            display_name=display_name,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def set_verified(self, user_id: uuid.UUID) -> None:
        user = await self.get_by_id(user_id)
        if user:
            user.is_verified = True
            await self._session.flush()
