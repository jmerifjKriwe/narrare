"""Session error-handling tests — extracted from ``test_session_manager.py``
(RULE-04 split).

Q-017: a missing/expired session raises the typed
:class:`SessionNotFoundError` (a :class:`NotFoundError`), NOT a bare
``ValueError``. This lets catch sites distinguish the benign end_session race
from cache corruption (``json.JSONDecodeError``).

Lifecycle / history / persistence / serialization tests stay in
``test_session_manager.py``; this file owns the error contract.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from narrare_core.shared.errors import NotFoundError, SessionNotFoundError
from narrare_core.writing.session_manager import SessionManager

# ---------------------------------------------------------------------------
# In-memory cache stub (module-local — no I/O, no Redis)
# ---------------------------------------------------------------------------


class InMemoryCache:
    """Simple dict-backed cache for unit tests."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._data[key] = value

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Graceful handling of missing/expired sessions.

    Q-017: a missing/expired session raises the typed
    :class:`SessionNotFoundError` (a :class:`NotFoundError`), NOT a bare
    ``ValueError``. This lets catch sites distinguish the benign
    end_session race from cache corruption (``json.JSONDecodeError``).
    """

    async def test_add_message_to_nonexistent_session_raises_session_not_found(
        self, manager: SessionManager
    ) -> None:
        with pytest.raises(SessionNotFoundError, match="not found or expired"):
            await manager.add_message(uuid4(), "user", "Hello")

    async def test_session_not_found_is_a_not_found_error(self, manager: SessionManager) -> None:
        # Generic NotFoundError handlers must still match (Liskov).
        with pytest.raises(NotFoundError):
            await manager.add_message(uuid4(), "user", "Hello")

    async def test_session_not_found_is_not_a_value_error(self, manager: SessionManager) -> None:
        # Q-017 design decision: deliberately NOT a ValueError subclass, so
        # stale ``except ValueError`` sites cannot silently keep catching it.
        assert not issubclass(SessionNotFoundError, ValueError)
        # Behaviourally: a bare ``except ValueError`` does not swallow it.
        with pytest.raises(SessionNotFoundError):
            await manager.append_prose(uuid4(), "Some text")

    async def test_append_prose_to_nonexistent_session_raises(
        self, manager: SessionManager
    ) -> None:
        with pytest.raises(SessionNotFoundError, match="not found or expired"):
            await manager.append_prose(uuid4(), "Some text")

    async def test_save_to_chapter_nonexistent_session_raises(
        self, manager: SessionManager
    ) -> None:
        with pytest.raises(SessionNotFoundError, match="not found or expired"):
            await manager.save_to_chapter(uuid4())

    async def test_corrupt_cache_payload_is_distinct_from_missing_session(
        self, manager: SessionManager, cache: InMemoryCache
    ) -> None:
        """A corrupt cached payload must NOT be conflated with a missing
        session (Q-017 RULE-11 regression guard).

        Corruption surfaces as ``json.JSONDecodeError`` (a ``ValueError``
        subclass, but NOT a ``SessionNotFoundError``) — the whole point of
        the typed exception is that catch sites can tell them apart.
        """
        session_id = uuid4()
        cache._data[f"writing:session:{session_id}"] = "{this is not valid json"

        # Corruption is its own error, not the benign missing-session type.
        with pytest.raises(json.JSONDecodeError):
            await manager.add_message(session_id, "user", "Hello")
        # Confirm it is genuinely not the typed not-found error:
        with pytest.raises(json.JSONDecodeError):
            try:
                await manager.add_message(session_id, "user", "Hello")
            except SessionNotFoundError:  # pragma: no cover - regression
                pytest.fail("corruption was swallowed as SessionNotFoundError")
