"""Unit tests for KBCreationSessionStore — session storage cache backend.

Tests CRUD operations, key formatting, TTL propagation,
and update behaviour (extends TTL via re-set).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from narrare.kb.session_models import KBCreationField, KBCreationSession
from narrare.kb.session_store import (
    KBCreationSessionStore,
)
from narrare_core.writing.session_manager import SessionCacheProtocol

# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------


class FakeSessionCache:
    """In-memory fake for SessionCacheProtocol.

    Records all operations for assertion.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._ttls: dict[str, int] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._data[key] = value
        if ttl_seconds is not None:
            self._ttls[key] = ttl_seconds
        self.set_calls.append((key, value, ttl_seconds))

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._ttls.pop(key, None)


def _make_session(
    entity_type: str = "character",
    status: str = "active",
    name: str | None = None,
) -> KBCreationSession:
    """Create a minimal KBCreationSession for testing."""
    return KBCreationSession(
        id=uuid4(),
        novel_id=uuid4(),
        user_id=uuid4(),
        entity_type=entity_type,
        name=name,
        status=status,  # type: ignore[arg-type]
        fields=[
            KBCreationField(field_key="name", label="Name", required=True),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Key formatting
# ---------------------------------------------------------------------------


class TestSessionStoreKey:
    """Key format: ``kb:session:{session_id}``."""

    def test_key_format(self) -> None:
        """_key returns the correct prefix + UUID string."""
        backend = AsyncMock(spec=SessionCacheProtocol)
        store = KBCreationSessionStore(cache=backend)
        session_id = uuid4()

        key = store._key(session_id)

        assert key == f"kb:session:{session_id}"


# ---------------------------------------------------------------------------
# Create — store new session
# ---------------------------------------------------------------------------


class TestSessionStoreCreate:
    """``create()`` stores a new session with TTL."""

    @pytest.mark.asyncio
    async def test_create_stores_session(self) -> None:
        """Create stores the session JSON with correct key and TTL."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()

        result = await store.create(session)

        assert result.id == session.id
        assert result.entity_type == session.entity_type
        # Verify stored in backend
        key = f"kb:session:{session.id}"
        assert key in fake._data
        assert fake._ttls[key] == 1800

    @pytest.mark.asyncio
    async def test_create_returns_same_session(self) -> None:
        """Create returns the session unchanged."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()

        result = await store.create(session)

        assert result is session

    @pytest.mark.asyncio
    async def test_create_stores_valid_json(self) -> None:
        """Stored value is valid JSON that round-trips via model_validate_json."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()

        await store.create(session)

        key = f"kb:session:{session.id}"
        restored = KBCreationSession.model_validate_json(fake._data[key])
        assert restored.id == session.id
        assert restored.entity_type == session.entity_type


# ---------------------------------------------------------------------------
# Get — retrieve session
# ---------------------------------------------------------------------------


class TestSessionStoreGet:
    """``get()`` retrieves a session by ID."""

    @pytest.mark.asyncio
    async def test_get_returns_session_when_found(self) -> None:
        """Get returns a deserialized session when the key exists."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()
        await store.create(session)

        result = await store.get(session.id)

        assert result is not None
        assert result.id == session.id
        assert result.entity_type == session.entity_type

    @pytest.mark.asyncio
    async def test_get_returns_none_when_missing(self) -> None:
        """Get returns None when the session does not exist."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)

        result = await store.get(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_preserves_fields(self) -> None:
        """Get restores session fields correctly."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()
        session.fields.append(KBCreationField(field_key="role", label="Role", user_value="hero"))
        await store.create(session)

        result = await store.get(session.id)

        assert result is not None
        assert len(result.fields) == 2
        role_field = next(f for f in result.fields if f.field_key == "role")
        assert role_field.user_value == "hero"


# ---------------------------------------------------------------------------
# Update — modify and extend TTL
# ---------------------------------------------------------------------------


class TestSessionStoreUpdate:
    """``update()`` re-stores session and extends TTL."""

    @pytest.mark.asyncio
    async def test_update_stores_modified_session(self) -> None:
        """Update stores the modified session data."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()
        await store.create(session)

        session.name = "Aria"
        result = await store.update(session)

        assert result.name == "Aria"

    @pytest.mark.asyncio
    async def test_update_extends_ttl(self) -> None:
        """Update re-calls set with TTL, effectively extending it."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()
        await store.create(session)

        await store.update(session)

        key = f"kb:session:{session.id}"
        # The last set call should be the update with TTL
        last_call = fake.set_calls[-1]
        assert last_call[0] == key
        assert last_call[2] == 1800

    @pytest.mark.asyncio
    async def test_update_updates_timestamp(self) -> None:
        """Update sets updated_at to the current time."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()
        await store.create(session)

        result = await store.update(session)

        # updated_at is set to datetime.now(UTC) inside update()
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_returns_session(self) -> None:
        """Update returns the session with updated fields."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()
        await store.create(session)

        session.status = "review"  # type: ignore[assignment]
        result = await store.update(session)

        assert result.status == "review"


# ---------------------------------------------------------------------------
# Delete — remove session
# ---------------------------------------------------------------------------


class TestSessionStoreDelete:
    """``delete()`` removes a session from the store."""

    @pytest.mark.asyncio
    async def test_delete_removes_session(self) -> None:
        """Delete removes the session so subsequent get returns None."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()
        await store.create(session)

        await store.delete(session.id)
        result = await store.get(session.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_succeeds_silently(self) -> None:
        """Deleting a non-existent session does not raise."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)

        # Should not raise
        await store.delete(uuid4())


# ---------------------------------------------------------------------------
# Round-trip — full lifecycle
# ---------------------------------------------------------------------------


class TestSessionStoreLifecycle:
    """Full CRUD lifecycle test."""

    @pytest.mark.asyncio
    async def test_create_get_update_get_delete_get(self) -> None:
        """Full lifecycle: create → get → update → get → delete → get."""
        fake = FakeSessionCache()
        store = KBCreationSessionStore(cache=fake)
        session = _make_session()

        # Create
        await store.create(session)
        fetched = await store.get(session.id)
        assert fetched is not None
        assert fetched.entity_type == "character"

        # Update
        session.name = "Aria"
        session.status = "review"  # type: ignore[assignment]
        await store.update(session)
        fetched = await store.get(session.id)
        assert fetched is not None
        assert fetched.name == "Aria"
        assert fetched.status == "review"

        # Delete
        await store.delete(session.id)
        fetched = await store.get(session.id)
        assert fetched is None
