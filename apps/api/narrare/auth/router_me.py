"""Auth profile routes — GET /me for current user."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.auth.repository import AuthRepository
from narrare.auth.schemas import UserResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: CurrentUserIdDep,
    session: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    from uuid import UUID

    from narrare.settings.models import UserProvider

    repo = AuthRepository(session)
    uid = UUID(user_id)
    user = await repo.get_by_id(uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if user has any configured providers (determines setup completion)
    result = await session.execute(
        select(func.count()).select_from(UserProvider).where(UserProvider.user_id == uid)
    )
    provider_count = result.scalar() or 0

    resp = UserResponse.model_validate(user)
    resp.has_providers = provider_count > 0
    return resp
