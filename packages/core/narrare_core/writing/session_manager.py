"""Session manager for interactive writing flows.

Implements :class:`SessionManagerProtocol` from ``contracts.py``.
Uses an injected cache backend (in-memory per ADR-080; Redis re-plugs at
the :class:`SessionCacheProtocol` for multi-worker) for persistence —
core never imports the cache implementation directly (RULE-08).

See: docs/features/writing-session.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import structlog

from narrare_core.writing.models import SessionState
from narrare_core.writing.requests import (
    OwnershipMismatch,
    Reattached,
    ReattachOutcome,
    SessionExpired,
    SessionNotFound,
)
from narrare_core.writing.session_state_codec import (
    deserialize_session_state,
    serialize_session_state,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Cache protocol — injected by the API layer
# ---------------------------------------------------------------------------


class SessionCacheProtocol(Protocol):
    """Cache backend for session persistence.

    The API layer injects an in-memory implementation (per ADR-080).
    Redis can re-plug here for multi-worker deployments.  Core never
    imports the cache implementation directly (RULE-08).
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
    injects an in-memory implementation (per ADR-080; Redis re-plugs at
    the protocol for multi-worker).  Core never imports the cache
    implementation directly (RULE-08).
    """

    KEY_PREFIX = "writing:session:"

    def __init__(
        self,
        cache: SessionCacheProtocol,
        *,
        session_ttl_seconds: int = 30 * 60,
        max_history_messages: int = 20,
    ) -> None:
        self._cache = cache
        self._session_ttl_seconds = session_ttl_seconds
        self._max_history_messages = max_history_messages

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

    async def reattach_session(
        self,
        session_id: UUID,
        user_id: UUID,
        project_id: UUID,
    ) -> ReattachOutcome:
        """Reattach to an existing session after a transport reconnect (ADR-052).

        Pure-data validation: loads the cached state, checks liveness and
        ownership, and returns a typed :class:`ReattachOutcome` snapshot.
        Does NOT mutate the session's ``connection_state`` — the backend
        transport layer owns that transition.
        """
        # ``_load`` (not ``get_session``) so we can distinguish not-found
        # from inactive-expired: ``get_session`` collapses both to ``None``.
        state = await self._load(session_id)
        if state is None:
            logger.info(
                "reattach_not_found",
                session_id=str(session_id),
            )
            return SessionNotFound(session_id=session_id)
        if not state.is_active:
            logger.info(
                "reattach_expired",
                session_id=str(session_id),
            )
            return SessionExpired(session_id=session_id)
        if state.user_id != user_id or state.project_id != project_id:
            logger.warning(
                "reattach_ownership_mismatch",
                session_id=str(session_id),
                owner_user_id=str(state.user_id),
                owner_project_id=str(state.project_id),
            )
            return OwnershipMismatch(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
            )
        logger.info(
            "reattach_recovered",
            session_id=str(session_id),
            stream_status=state.stream_status.value,
            last_sequence=state.last_sequence,
        )
        return Reattached(
            session_id=state.session_id,
            chapter_id=state.chapter_id,
            project_id=state.project_id,
            user_id=state.user_id,
            stream_status=state.stream_status,
            last_sequence=state.last_sequence,
            active_partial_prose=state.active_partial_prose,
            active_invocation_id=state.active_invocation_id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _cache_key(self, session_id: UUID) -> str:
        return f"{self.KEY_PREFIX}{session_id}"

    def _serialize(self, state: SessionState) -> str:
        return serialize_session_state(state)

    def _deserialize(self, raw: str) -> SessionState:
        return deserialize_session_state(raw)

    async def _persist(self, state: SessionState) -> None:
        """Serialize and write to cache with TTL refresh."""
        key = self._cache_key(state.session_id)
        await self._cache.set(key, self._serialize(state), self._session_ttl_seconds)

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
        if len(state.conversation_history) <= self._max_history_messages:
            return

        system_msgs = [m for m in state.conversation_history if m.get("role") == "system"]
        non_system = [m for m in state.conversation_history if m.get("role") != "system"]

        # Keep newest non-system messages within budget
        budget = self._max_history_messages - len(system_msgs)
        if budget < 0:
            budget = 0
        trimmed = non_system[-budget:] if budget > 0 else []

        state.conversation_history = system_msgs + trimmed
