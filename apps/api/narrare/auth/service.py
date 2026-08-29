"""Auth service — business logic for registration, login, token refresh, profile."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    WsTicketResponse,
)
from narrare.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    needs_rehash,
    verify_password,
    verify_refresh_token,
)
from narrare.auth.ws_tickets import WS_TICKET_TTL
from narrare.auth.ws_tickets import issue as issue_ws_ticket_token
from narrare_core.shared.errors import AuthenticationError, ConflictError

if TYPE_CHECKING:
    import uuid

    from narrare._app.config import Settings
    from narrare.auth.contracts import AuthRepositoryProtocol, UserProvidersCountProtocol

logger = structlog.get_logger(__name__)


class AuthService:
    """Handles user registration, login, token refresh, and profile retrieval."""

    def __init__(
        self,
        repo: AuthRepositoryProtocol,
        settings: Settings,
        providers_repo: UserProvidersCountProtocol | None = None,
    ) -> None:
        self._repo = repo
        self._settings = settings
        self._providers_repo = providers_repo

    async def register(self, request: RegisterRequest) -> TokenResponse:
        """
        Register a new user and return tokens.

        Args:
            request: Registration data (email, password, display_name).

        Returns:
            TokenResponse with access and refresh tokens.

        Raises:
            ConflictError: If email is already registered.
        """
        existing = await self._repo.get_by_email(request.email)
        if existing is not None:
            raise ConflictError("Email already registered")

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
            AuthenticationError: If credentials are invalid.
        """
        user = await self._repo.get_by_email(request.email)

        # Constant-time comparison to prevent timing attacks
        if user is None or not verify_password(request.password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is disabled")

        # Rehash password if it uses outdated parameters or legacy algorithm
        if needs_rehash(user.hashed_password):
            try:
                new_hash = hash_password(request.password)
                await self._repo.update_hashed_password(user.id, new_hash)
                logger.info("password_rehashed", user_id=str(user.id))
            except Exception:
                # Log but don't block login (RULE-11: no silent failures)
                logger.warning("password_rehash_failed", user_id=str(user.id), exc_info=True)

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
            AuthenticationError: If refresh token is invalid or expired.
        """
        payload = verify_refresh_token(refresh_token, self._settings.secret_key)
        if payload is None:
            raise AuthenticationError("Invalid or expired refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token payload")

        # Verify user still exists and is active
        from uuid import UUID

        user = await self._repo.get_by_id(UUID(user_id))
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        return self._create_tokens(user_id)

    async def logout(self) -> None:
        """
        Log a logout event.

        This is a purely informational method — no server-side token
        invalidation is performed.  The caller (router) is responsible
        for clearing the httpOnly refresh cookie.
        """
        logger.info("user_logged_out")

    async def get_current_user_profile(self, user_id: uuid.UUID) -> UserResponse:
        """Fetch the current user's profile including provider status.

        Args:
            user_id: The authenticated user's UUID.

        Returns:
            UserResponse with profile data and ``has_providers`` flag.

        Raises:
            AuthenticationError: If the user does not exist.
        """
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found")

        has_providers = False
        if self._providers_repo is not None:
            count = await self._providers_repo.count_by_user(user_id)
            has_providers = count > 0

        resp = UserResponse.model_validate(user)
        resp.has_providers = has_providers
        return resp

    def issue_ws_ticket(self, user_id: uuid.UUID) -> WsTicketResponse:
        """Mint a single-use WebSocket handshake ticket bound to ``user_id``.

        Backs ``POST /api/v1/auth/ws-ticket`` (ADR-084): the raw token is
        returned exactly once and never stored; the WS handshake derives
        the session identity by consuming it.

        Args:
            user_id: The JWT-authenticated user (``CurrentUserIdDep``).

        Returns:
            WsTicketResponse with the opaque token and its TTL in seconds.
        """
        return WsTicketResponse(
            token=issue_ws_ticket_token(user_id),
            expires_in=int(WS_TICKET_TTL.total_seconds()),
        )

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
