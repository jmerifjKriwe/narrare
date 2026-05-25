"""KB creation session storage — Redis-backed with TTL.

Uses SessionCacheProtocol (injected Redis) following RULE-08.
Sessions are ephemeral — 30min TTL, auto-deleted on abandonment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from .session_models import KBCreationSession

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.writing.session_manager import SessionCacheProtocol

logger = structlog.get_logger(__name__)

SESSION_TTL = 1800  # 30 minutes
SESSION_KEY_PREFIX = "kb:session:"


class KBCreationSessionStore:
    """Redis-backed ephemeral storage for KB creation sessions.

    Args:
        cache: Injected cache backend (Redis in production).
    """

    def __init__(self, cache: SessionCacheProtocol) -> None:
        self._cache = cache

    def _key(self, session_id: UUID) -> str:
        return f"{SESSION_KEY_PREFIX}{session_id}"

    async def create(self, session: KBCreationSession) -> KBCreationSession:
        """Store a new session with TTL."""
        key = self._key(session.id)
        await self._cache.set(key, session.model_dump_json(), ttl_seconds=SESSION_TTL)
        logger.info(
            "kb_session_created",
            session_id=str(session.id),
            entity_type=session.entity_type,
        )
        return session

    async def get(self, session_id: UUID) -> KBCreationSession | None:
        """Retrieve a session by ID. Returns None if not found."""
        key = self._key(session_id)
        data = await self._cache.get(key)
        if data is None:
            return None
        return KBCreationSession.model_validate_json(data)

    async def update(self, session: KBCreationSession) -> KBCreationSession:
        """Update an existing session (extends TTL)."""
        session.updated_at = datetime.now(UTC)
        key = self._key(session.id)
        await self._cache.set(key, session.model_dump_json(), ttl_seconds=SESSION_TTL)
        logger.debug(
            "kb_session_updated",
            session_id=str(session.id),
            status=session.status,
        )
        return session

    async def delete(self, session_id: UUID) -> None:
        """Delete a session."""
        key = self._key(session_id)
        await self._cache.delete(key)
        logger.info("kb_session_deleted", session_id=str(session_id))
