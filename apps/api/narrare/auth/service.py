"""Auth service — business logic for registration, login, token refresh."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import HTTPException, status

from narrare.auth.repository import AuthRepository
from narrare.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from narrare.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare._app.config import Settings

logger = structlog.get_logger(__name__)


class AuthService:
    """Handles user registration, login, and token refresh."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._repo = AuthRepository(session)
        self._settings = settings

    async def register(self, request: RegisterRequest) -> TokenResponse:
        """
        Register a new user and return tokens.

        Args:
            request: Registration data (email, password, display_name).

        Returns:
            TokenResponse with access and refresh tokens.

        Raises:
            HTTPException 409: If email is already registered.
        """
        existing = await self._repo.get_by_email(request.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        hashed = hash_password(request.password)
        user = await self._repo.create(
            email=request.email,
            hashed_password=hashed,
            display_name=request.display_name,
        )

        logger.info("user_registered", user_id=str(user.id))
        return self._create_tokens(str(user.id))

    async def login(self, request: LoginRequest) -> TokenResponse:
        """
        Authenticate a user and return tokens.

        Args:
            request: Login credentials (email, password).

        Returns:
            TokenResponse with access and refresh tokens.

        Raises:
            HTTPException 401: If credentials are invalid.
        """
        user = await self._repo.get_by_email(request.email)

        # Constant-time comparison to prevent timing attacks
        if not user or not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled",
            )

        logger.info("user_logged_in", user_id=str(user.id))
        return self._create_tokens(str(user.id))

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """
        Issue new tokens from a valid refresh token.

        Args:
            refresh_token: A valid refresh JWT.

        Returns:
            New TokenResponse with fresh access and refresh tokens.

        Raises:
            HTTPException 401: If refresh token is invalid or expired.
        """
        payload = verify_refresh_token(refresh_token, self._settings.secret_key)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Verify user still exists and is active
        from uuid import UUID

        user = await self._repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        return self._create_tokens(user_id)

    def _create_tokens(self, user_id: str) -> TokenResponse:
        """Create access + refresh token pair."""
        access = create_access_token(
            subject=user_id,
            secret_key=self._settings.secret_key,
            expires_minutes=self._settings.access_token_expire_minutes,
        )
        refresh = create_refresh_token(
            subject=user_id,
            secret_key=self._settings.secret_key,
            expires_days=self._settings.refresh_token_expire_days,
        )
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=self._settings.access_token_expire_minutes * 60,
        )
