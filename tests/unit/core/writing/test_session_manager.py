"""Tests for SessionManager — writing session lifecycle.

Covers:
- Session lifecycle: create → add_message → get → end
- History management: cap at 20 messages, trim oldest
- Expired/missing session returns None
- Save to chapter: returns prose buffer content
- Empty buffer save: raises ValueError
- TTL refresh on each message
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from narrare_core.writing.session_manager import SessionManager

# ---------------------------------------------------------------------------
# In-memory cache stub (no I/O, no Redis)
# ---------------------------------------------------------------------------


class InMemoryCache:
    """Simple dict-backed cache for unit tests."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.last_ttl: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._data[key] = value
        self.last_ttl[key] = ttl_seconds

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cache() -> InMemoryCache:
    return InMemoryCache()


@pytest.fixture
def manager(cache: InMemoryCache) -> SessionManager:
    return SessionManager(cache=cache)


def _uuids() -> tuple[UUID, UUID, UUID]:
    """Return (chapter_id, project_id, user_id) as UUIDs."""
    return uuid4(), uuid4(), uuid4()


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    """Full session lifecycle: create → add_message → get → end."""

    async def test_create_session_returns_uuid(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)
        assert isinstance(session_id, type(uuid4()))

    async def test_create_session_persists_state(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        state = await manager.get_session(session_id)
        assert state is not None
        assert state.chapter_id == chapter_id
        assert state.project_id == project_id
        assert state.user_id == user_id
        assert state.is_active is True
        assert state.prose_buffer == ""
        assert state.conversation_history == []

    async def test_add_message_and_retrieve(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        await manager.add_message(session_id, "system", "You are a writer.")
        await manager.add_message(session_id, "user", "Write me a scene.")

        state = await manager.get_session(session_id)
        assert state is not None
        assert len(state.conversation_history) == 2
        assert state.conversation_history[0] == {"role": "system", "content": "You are a writer."}
        assert state.conversation_history[1] == {"role": "user", "content": "Write me a scene."}

    async def test_end_session_marks_inactive_and_deletes(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        await manager.end_session(session_id)

        # get_session should return None for ended session
        state = await manager.get_session(session_id)
        assert state is None

    async def test_end_nonexistent_session_no_error(self, manager: SessionManager) -> None:
        # Should not raise — graceful handling
        await manager.end_session(uuid4())

    async def test_get_session_nonexistent_returns_none(self, manager: SessionManager) -> None:
        state = await manager.get_session(uuid4())
        assert state is None


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------


class TestHistoryManagement:
    """Message cap at 20, trimming oldest, preserving system messages."""

    async def test_history_capped_at_twenty(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        # Add 25 user messages
        for i in range(25):
            await manager.add_message(session_id, "user", f"Message {i}")

        state = await manager.get_session(session_id)
        assert state is not None
        assert len(state.conversation_history) == 20

    async def test_trim_preserves_system_messages(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        # Add 2 system messages
        await manager.add_message(session_id, "system", "System 1")
        await manager.add_message(session_id, "system", "System 2")

        # Add 20 user messages (total = 22, should trim to 20)
        for i in range(20):
            await manager.add_message(session_id, "user", f"Message {i}")

        state = await manager.get_session(session_id)
        assert state is not None
        assert len(state.conversation_history) == 20

        # System messages should be preserved
        system_msgs = [m for m in state.conversation_history if m["role"] == "system"]
        assert len(system_msgs) == 2

        # Newest user messages should be kept
        user_msgs = [m for m in state.conversation_history if m["role"] == "user"]
        assert len(user_msgs) == 18
        # Most recent user message
        assert user_msgs[-1]["content"] == "Message 19"

    async def test_no_trim_when_under_limit(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        # Add 10 messages — under the 20 cap
        for i in range(10):
            await manager.add_message(session_id, "user", f"Message {i}")

        state = await manager.get_session(session_id)
        assert state is not None
        assert len(state.conversation_history) == 10


# ---------------------------------------------------------------------------
# TTL and persistence
# ---------------------------------------------------------------------------


class TestTTLPersistence:
    """TTL is refreshed on each write, cache key format is correct."""

    async def test_ttl_set_on_create(self, manager: SessionManager, cache: InMemoryCache) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        key = f"writing:session:{session_id}"
        assert key in cache.last_ttl
        assert cache.last_ttl[key] == 30 * 60  # 30 minutes

    async def test_ttl_refreshed_on_add_message(
        self, manager: SessionManager, cache: InMemoryCache
    ) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        # Reset TTL tracking
        cache.last_ttl.clear()
        await manager.add_message(session_id, "user", "Hello")

        key = f"writing:session:{session_id}"
        assert cache.last_ttl[key] == 30 * 60

    async def test_ttl_refreshed_on_append_prose(
        self, manager: SessionManager, cache: InMemoryCache
    ) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        cache.last_ttl.clear()
        await manager.append_prose(session_id, "Some prose text.")

        key = f"writing:session:{session_id}"
        assert cache.last_ttl[key] == 30 * 60


# ---------------------------------------------------------------------------
# Prose buffer operations
# ---------------------------------------------------------------------------


class TestProseBuffer:
    """Prose buffer accumulate, save_to_chapter, clear."""

    async def test_append_prose_accumulates(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        await manager.append_prose(session_id, "First paragraph.")
        await manager.append_prose(session_id, "Second paragraph.")

        state = await manager.get_session(session_id)
        assert state is not None
        assert "First paragraph." in state.prose_buffer
        assert "Second paragraph." in state.prose_buffer
        # Paragraphs joined with double newline
        assert state.prose_buffer == "First paragraph.\n\nSecond paragraph."

    async def test_append_prose_first_append_no_leading_newline(
        self, manager: SessionManager
    ) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        await manager.append_prose(session_id, "Just text.")

        state = await manager.get_session(session_id)
        assert state is not None
        assert state.prose_buffer == "Just text."

    async def test_save_to_chapter_returns_buffer_content(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        await manager.append_prose(session_id, "Chapter content here.")
        result = await manager.save_to_chapter(session_id)

        assert result == "Chapter content here."

    async def test_save_to_chapter_preserves_buffer(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        await manager.append_prose(session_id, "Content that persists.")
        await manager.save_to_chapter(session_id)

        state = await manager.get_session(session_id)
        assert state is not None
        assert state.prose_buffer == "Content that persists."

    async def test_save_to_chapter_empty_buffer_raises(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        with pytest.raises(ValueError, match="Prose buffer is empty"):
            await manager.save_to_chapter(session_id)


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    """SessionState serializes/deserializes correctly through cache."""

    async def test_round_trip_preserves_all_fields(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        await manager.add_message(session_id, "user", "Test message")
        await manager.append_prose(session_id, "Some prose.")

        state = await manager.get_session(session_id)
        assert state is not None

        # Verify all fields survived the round-trip
        assert state.session_id == session_id
        assert state.chapter_id == chapter_id
        assert state.project_id == project_id
        assert state.user_id == user_id
        assert len(state.conversation_history) == 1
        assert state.prose_buffer == "Some prose."
        assert isinstance(state.started_at, datetime)
        assert isinstance(state.last_activity, datetime)
        assert state.is_active is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Graceful handling of missing/expired sessions."""

    async def test_add_message_to_nonexistent_session_raises(self, manager: SessionManager) -> None:
        with pytest.raises(ValueError, match="not found or expired"):
            await manager.add_message(uuid4(), "user", "Hello")

    async def test_append_prose_to_nonexistent_session_raises(
        self, manager: SessionManager
    ) -> None:
        with pytest.raises(ValueError, match="not found or expired"):
            await manager.append_prose(uuid4(), "Some text")

    async def test_save_to_chapter_nonexistent_session_raises(
        self, manager: SessionManager
    ) -> None:
        with pytest.raises(ValueError, match="not found or expired"):
            await manager.save_to_chapter(uuid4())
