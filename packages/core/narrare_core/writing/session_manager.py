"""Session manager for interactive writing flows.

Implements :class:`SessionManagerProtocol` from ``contracts.py``.
Uses an injected cache backend (Redis in production) for persistence —
core never imports Redis directly (RULE-08).

See: docs/features/writing-session.md
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import structlog

from narrare_core.writing.models import SessionState

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Cache protocol — injected by the API layer
# ---------------------------------------------------------------------------


class SessionCacheProtocol(Protocol):
    """Cache backend for session persistence.

    The API layer injects a Redis-backed implementation.  Core never
    imports Redis directly (RULE-08).
    """

    async def get(self, key: str) -> str | None:
        """Get a cached value."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set a cached value with optional TTL."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a cached value."""
        ...


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------


class SessionManager:
    """Manages interactive writing session state.

    Uses a :class:`SessionCacheProtocol` for persistence — the API layer
    injects a Redis-backed implementation.  Core never imports Redis
    directly (RULE-08).
    """

    SESSION_TTL_SECONDS = 30 * 60  # 30 minutes
    MAX_HISTORY_MESSAGES = 20
    KEY_PREFIX = "writing:session:"

    def __init__(self, cache: SessionCacheProtocol) -> None:
        self._cache = cache

    # ------------------------------------------------------------------
    # Public API (implements SessionManagerProtocol)
    # ------------------------------------------------------------------

    async def create_session(
        self,
        chapter_id: UUID,
        project_id: UUID,
        user_id: UUID,
    ) -> UUID:
        """Create a new interactive session, return session ID.

        Persists the initial :class:`SessionState` to cache with a
        30-minute TTL.
        """
        session_id = uuid4()
        state = SessionState(
            session_id=session_id,
            chapter_id=chapter_id,
            project_id=project_id,
            user_id=user_id,
        )

        await self._persist(state)
        logger.info(
            "session_created",
            session_id=str(session_id),
            chapter_id=str(chapter_id),
        )
        return session_id

    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
    ) -> None:
        """Add a message to session history.

        Enforces the 20-message cap by trimming oldest messages while
        preserving system messages.  Refreshes the TTL on each write.
        """
        state = await self._load_or_raise(session_id)
        state.conversation_history.append({"role": role, "content": content})
        state.last_activity = datetime.now(UTC)
        self._trim_history(state)
        await self._persist(state)

    async def get_session(self, session_id: UUID) -> SessionState | None:
        """Retrieve current session state.

        Returns ``None`` if the session does not exist, has expired, or
        is inactive.
        """
        state = await self._load(session_id)
        if state is None:
            return None
        if not state.is_active:
            return None
        return state

    async def append_prose(
        self,
        session_id: UUID,
        text: str,
    ) -> None:
        """Append accepted text to the prose buffer."""
        state = await self._load_or_raise(session_id)
        if state.prose_buffer:
            state.prose_buffer += "\n\n" + text
        else:
            state.prose_buffer = text
        state.last_activity = datetime.now(UTC)
        await self._persist(state)

    async def save_to_chapter(self, session_id: UUID) -> str:
        """Save prose buffer as chapter draft, return content.

        Raises :class:`ValueError` if the prose buffer is empty.
        The prose buffer is preserved — call :meth:`end_session` to
        clear it.
        """
        state = await self._load_or_raise(session_id)
        if not state.prose_buffer:
            raise ValueError("Prose buffer is empty — nothing to save.")
        return state.prose_buffer

    async def end_session(self, session_id: UUID) -> None:
        """End session and clean up.

        Marks the session as inactive and deletes it from cache.
        """
        state = await self._load(session_id)
        if state is None:
            logger.warning("session_end_not_found", session_id=str(session_id))
            return

        state.is_active = False
        key = self._cache_key(session_id)
        await self._cache.delete(key)
        logger.info("session_ended", session_id=str(session_id))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _cache_key(self, session_id: UUID) -> str:
        return f"{self.KEY_PREFIX}{session_id}"

    def _serialize(self, state: SessionState) -> str:
        data = {
            "session_id": str(state.session_id),
            "chapter_id": str(state.chapter_id),
            "project_id": str(state.project_id),
            "user_id": str(state.user_id),
            "conversation_history": state.conversation_history,
            "prose_buffer": state.prose_buffer,
            "started_at": state.started_at.isoformat(),
            "last_activity": state.last_activity.isoformat(),
            "is_active": state.is_active,
        }
        return json.dumps(data)

    def _deserialize(self, raw: str) -> SessionState:
        data = json.loads(raw)
        return SessionState(
            session_id=UUID(data["session_id"]),
            chapter_id=UUID(data["chapter_id"]),
            project_id=UUID(data["project_id"]),
            user_id=UUID(data["user_id"]),
            conversation_history=data["conversation_history"],
            prose_buffer=data["prose_buffer"],
            started_at=datetime.fromisoformat(data["started_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            is_active=data["is_active"],
        )

    async def _persist(self, state: SessionState) -> None:
        """Serialize and write to cache with TTL refresh."""
        key = self._cache_key(state.session_id)
        await self._cache.set(key, self._serialize(state), self.SESSION_TTL_SECONDS)

    async def _load(self, session_id: UUID) -> SessionState | None:
        """Load session from cache, returning None if missing."""
        key = self._cache_key(session_id)
        raw = await self._cache.get(key)
        if raw is None:
            return None
        return self._deserialize(raw)

    async def _load_or_raise(self, session_id: UUID) -> SessionState:
        """Load session from cache, raising if not found."""
        state = await self._load(session_id)
        if state is None:
            raise ValueError(f"Session {session_id} not found or expired.")
        return state

    def _trim_history(self, state: SessionState) -> None:
        """Enforce the message cap, preserving system messages."""
        if len(state.conversation_history) <= self.MAX_HISTORY_MESSAGES:
            return

        system_msgs = [m for m in state.conversation_history if m.get("role") == "system"]
        non_system = [m for m in state.conversation_history if m.get("role") != "system"]

        # Keep newest non-system messages within budget
        budget = self.MAX_HISTORY_MESSAGES - len(system_msgs)
        if budget < 0:
            budget = 0
        trimmed = non_system[-budget:] if budget > 0 else []

        state.conversation_history = system_msgs + trimmed
