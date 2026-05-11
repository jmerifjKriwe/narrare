"""Auth service contracts (Protocols) — written before implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.auth.models import User
    from narrare.auth.schemas import LoginRequest, RegisterRequest, TokenResponse


@runtime_checkable
class AuthRepositoryProtocol(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...
    async def create(self, email: str, hashed_password: str, display_name: str) -> User: ...
    async def set_verified(self, user_id: uuid.UUID) -> None: ...


@runtime_checkable
class AuthServiceProtocol(Protocol):
    async def register(self, request: RegisterRequest) -> TokenResponse: ...
    async def login(self, request: LoginRequest) -> TokenResponse: ...
    async def refresh(self, refresh_token: str) -> TokenResponse: ...
