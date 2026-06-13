"""Unit tests for ``narrare._app.database`` — session lifecycle and engine.

Tests the database session factory, engine access, and disposal with fake
objects so no real database connection is needed.
"""

from __future__ import annotations

from typing import Any

import pytest

import narrare._app.database as db_mod

# ---------------------------------------------------------------------------
# Fake objects
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal async session with commit/rollback tracking."""

    def __init__(self) -> None:
        self.committed: bool = False
        self.rolled_back: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeSessionContext:
    """Async context manager wrapping a fake session."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *args: Any) -> None:
        pass


class _FakeSessionFactory:
    """Callable returning an async context manager for a session."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionContext:
        return _FakeSessionContext(self._session)


class _FakeEngine:
    """Fake async engine with dispose tracking."""

    def __init__(self) -> None:
        self.disposed: bool = False

    async def dispose(self) -> None:
        self.disposed = True


# ---------------------------------------------------------------------------
# get_async_session — commit path
# ---------------------------------------------------------------------------


class TestGetAsyncSessionCommit:
    async def test_session_commits_on_normal_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = _FakeSession()
        monkeypatch.setattr(db_mod, "_async_session_factory", _FakeSessionFactory(session))

        gen = db_mod.get_async_session()
        result = await gen.__anext__()
        assert result is session

        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

        assert session.committed is True
        assert session.rolled_back is False


# ---------------------------------------------------------------------------
# get_async_session — rollback path
# ---------------------------------------------------------------------------


class TestGetAsyncSessionRollback:
    async def test_session_rolls_back_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = _FakeSession()
        monkeypatch.setattr(db_mod, "_async_session_factory", _FakeSessionFactory(session))

        gen = db_mod.get_async_session()
        result = await gen.__anext__()
        assert result is session

        with pytest.raises(ValueError):
            await gen.athrow(ValueError("test"))

        assert session.rolled_back is True
        assert session.committed is False


# ---------------------------------------------------------------------------
# get_session_factory
# ---------------------------------------------------------------------------


class TestGetSessionFactory:
    def test_returns_module_level_factory(self) -> None:
        factory = db_mod.get_session_factory()
        assert factory is db_mod._async_session_factory


# ---------------------------------------------------------------------------
# get_engine
# ---------------------------------------------------------------------------


class TestGetEngine:
    async def test_returns_module_level_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_engine = _FakeEngine()
        monkeypatch.setattr(db_mod, "_engine", fake_engine)

        engine = await db_mod.get_engine()
        assert engine is fake_engine


# ---------------------------------------------------------------------------
# dispose_database
# ---------------------------------------------------------------------------


class TestDisposeDatabase:
    async def test_disposes_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_engine = _FakeEngine()
        monkeypatch.setattr(db_mod, "_engine", fake_engine)

        await db_mod.dispose_database()

        assert fake_engine.disposed


# ---------------------------------------------------------------------------
# _create_engine — non-test path (line 45)
# ---------------------------------------------------------------------------


class _NonTestSettings:
    """Settings stub with non-test environment and pool attributes."""

    is_test = False
    active_database_url = "postgresql+asyncpg://test:5432/db"
    db_pool_size = 5
    db_max_overflow = 10
    db_echo = False


class TestCreateEngineNonTest:
    def test_uses_pool_settings_when_not_test(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-test environment creates engine with pool settings."""
        monkeypatch.setattr(db_mod, "get_settings", lambda: _NonTestSettings())

        captured: dict[str, Any] = {}

        def _fake_create(*_args: Any, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return "fake-engine"

        monkeypatch.setattr(db_mod, "create_async_engine", _fake_create)

        engine = db_mod._create_engine()

        assert engine == "fake-engine"
        assert captured["pool_size"] == 5
        assert captured["max_overflow"] == 10
        assert captured["pool_pre_ping"] is True
        assert captured["echo"] is False
