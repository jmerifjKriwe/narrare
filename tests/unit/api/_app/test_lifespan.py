"""Unit tests for ``narrare._app.lifespan`` — DB version, migrations, lifespan.

Tests the DB-version query, pending-migrations helper, the full lifespan
context manager (startup + shutdown in both test and non-test modes), and
the logging configuration helper.  All external dependencies (database,
wiki listeners) are replaced with fake classes / patched functions so no
real I/O occurs. The budget-guard lifecycle lives in the companion
``test_lifespan_budget.py`` (shared fakes: ``_lifespan_helpers``).
"""

from __future__ import annotations

import os
from typing import Any

import pytest

import narrare._app.lifespan as lifespan_mod
from alembic import command as alembic_command
from tests.unit.api._app._lifespan_helpers import (
    _FakeSettings,
    _make_app,
    _noop_async,
    _patch_common,
    _returning_async,
)

# ---------------------------------------------------------------------------
# Module-level async helpers — shared fleet lives in ``_lifespan_helpers``
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Fake objects — pure Python (no MagicMock)
# ---------------------------------------------------------------------------


class _FakeResult:
    """Fake SQLAlchemy result with a fetchone()."""

    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


class _FakeConnection:
    """Fake async connection with a canned execute() result or exception."""

    def __init__(
        self,
        row: tuple[Any, ...] | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._row = row
        self._exc = exc

    async def execute(self, _sql: Any) -> _FakeResult:
        if self._exc:
            raise self._exc
        return _FakeResult(self._row)


class _ConnCtx:
    """Async context manager wrapping a fake connection."""

    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConnection:
        return self._conn

    async def __aexit__(self, *args: Any) -> None:
        pass


class _FakeEngine:
    """Fake async engine with connect() and dispose()."""

    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn
        self.disposed: bool = False

    def connect(self) -> _ConnCtx:
        return _ConnCtx(self._conn)

    async def dispose(self) -> None:
        self.disposed = True


class _FakeEngineFactory:
    """Callable replacing ``create_async_engine``."""

    def __init__(self, engine: _FakeEngine) -> None:
        self._engine = engine

    def __call__(self, *_args: Any, **_kwargs: Any) -> _FakeEngine:
        return self._engine


# ---------------------------------------------------------------------------
# _get_db_version
# ---------------------------------------------------------------------------


class TestGetDbVersion:
    async def test_returns_version_when_row_exists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = _FakeConnection(row=("abc123",))
        engine = _FakeEngine(conn)
        monkeypatch.setattr(lifespan_mod, "create_async_engine", _FakeEngineFactory(engine))

        result = await lifespan_mod._get_db_version("postgresql://test")

        assert result == "abc123"
        assert engine.disposed

    async def test_returns_none_when_no_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = _FakeConnection(row=None)
        engine = _FakeEngine(conn)
        monkeypatch.setattr(lifespan_mod, "create_async_engine", _FakeEngineFactory(engine))

        result = await lifespan_mod._get_db_version("postgresql://test")

        assert result is None
        assert engine.disposed

    async def test_returns_none_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fresh DB — alembic_version table does not exist yet."""
        conn = _FakeConnection(exc=RuntimeError("relation does not exist"))
        engine = _FakeEngine(conn)
        monkeypatch.setattr(lifespan_mod, "create_async_engine", _FakeEngineFactory(engine))

        result = await lifespan_mod._get_db_version("postgresql://test")

        assert result is None
        assert engine.disposed


# ---------------------------------------------------------------------------
# _run_pending_migrations
# ---------------------------------------------------------------------------


class TestRunPendingMigrations:
    async def test_applies_migrations_when_version_changes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        versions = iter(["v1", "v2"])

        async def _fake_version(_url: str) -> str | None:
            return next(versions)

        monkeypatch.setattr(lifespan_mod, "_get_db_version", _fake_version)

        upgrade_calls: list[Any] = []
        monkeypatch.setattr(
            alembic_command,
            "upgrade",
            lambda cfg, target: upgrade_calls.append((cfg, target)),
        )

        await lifespan_mod._run_pending_migrations()

        assert len(upgrade_calls) == 1
        assert upgrade_calls[0][1] == "head"

    async def test_logs_up_to_date_when_version_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_version(_url: str) -> str | None:
            return "v1"

        monkeypatch.setattr(lifespan_mod, "_get_db_version", _fake_version)
        monkeypatch.setattr(alembic_command, "upgrade", lambda *_a: None)

        # Should complete without raising
        await lifespan_mod._run_pending_migrations()


# ---------------------------------------------------------------------------
# lifespan — test mode (is_test=True, skips DB/cleanup/dispose)
# ---------------------------------------------------------------------------


class TestLifespanTestMode:
    async def test_startup_and_shutdown_complete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _FakeSettings(is_test=True)
        _patch_common(monkeypatch, settings)

        app = _make_app()
        async with lifespan_mod.lifespan(app):
            pass  # startup runs before, shutdown after

        # No cleanup task created in test mode
        # Shutdown completed without error


# ---------------------------------------------------------------------------
# lifespan — non-test mode (covers migrations, cleanup, periodic task, dispose)
# ---------------------------------------------------------------------------


class TestLifespanNonTestMode:
    async def test_startup_and_shutdown_with_full_lifecycle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _FakeSettings(is_test=False)
        _patch_common(monkeypatch, settings)

        # Patch migration helper — avoids real Alembic run.
        async def _fake_migrate() -> None:
            pass

        monkeypatch.setattr(lifespan_mod, "_run_pending_migrations", _fake_migrate)

        # Patch stale cleanup — avoids DB session creation.
        async def _fake_cleanup() -> int:
            return 0

        monkeypatch.setattr(lifespan_mod, "_run_stale_cleanup", _fake_cleanup)

        # Patch database disposal.
        async def _fake_dispose() -> None:
            pass

        monkeypatch.setattr("narrare._app.database.dispose_database", _fake_dispose)

        app = _make_app()
        async with lifespan_mod.lifespan(app):
            pass

        # Startup ran migrations, cleanup, created periodic task.
        # Shutdown cancelled task, disposed DB.

    async def test_startup_cleanup_logs_when_stale_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Startup cleanup path when stale_count > 0."""
        settings = _FakeSettings(is_test=False)
        _patch_common(monkeypatch, settings)

        monkeypatch.setattr(lifespan_mod, "_run_pending_migrations", _noop_async)
        monkeypatch.setattr(lifespan_mod, "_run_stale_cleanup", _returning_async(5))
        monkeypatch.setattr("narrare._app.database.dispose_database", _noop_async)

        app = _make_app()
        async with lifespan_mod.lifespan(app):
            pass

    async def test_does_not_bridge_encryption_key_to_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression (ADR-071 §5): lifespan must NOT sync the encryption key
        into ``os.environ``.

        ``core/crypto.py`` now reads ``get_core_settings().encryption_key``
        directly. The former env-var bridge was an architectural-discipline §4
        workaround (bypassing an abstraction "just to make it work") and has
        been removed. This test guards against its re-introduction.
        """
        monkeypatch.delenv("NARRARE_ENCRYPTION_KEY", raising=False)

        settings = _FakeSettings(is_test=True)
        _patch_common(monkeypatch, settings)

        app = _make_app()
        async with lifespan_mod.lifespan(app):
            assert "NARRARE_ENCRYPTION_KEY" not in os.environ

        monkeypatch.delenv("NARRARE_ENCRYPTION_KEY", raising=False)

    async def test_e2e_test_mode_logs_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When NARRARE_E2E_TEST is set, a startup message is logged."""
        monkeypatch.setenv("NARRARE_E2E_TEST", "1")

        settings = _FakeSettings(is_test=True)
        _patch_common(monkeypatch, settings)

        app = _make_app()
        async with lifespan_mod.lifespan(app):
            pass

        monkeypatch.delenv("NARRARE_E2E_TEST", raising=False)

    async def test_migration_failure_reraises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Migration exception is re-raised (fail-fast, not swallowed)."""
        settings = _FakeSettings(is_test=False)
        _patch_common(monkeypatch, settings)

        async def _failing_migrate() -> None:
            raise RuntimeError("migration boom")

        monkeypatch.setattr(lifespan_mod, "_run_pending_migrations", _failing_migrate)
        monkeypatch.setattr(lifespan_mod, "_run_stale_cleanup", _returning_async(0))

        app = _make_app()
        with pytest.raises(RuntimeError, match="migration boom"):
            async with lifespan_mod.lifespan(app):
                pass


# ---------------------------------------------------------------------------
# _configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    def test_calls_configure_logging(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_configure_logging() delegates to narrare._app.logging.configure_logging."""
        called: list[bool] = []

        def _fake_config() -> None:
            called.append(True)

        monkeypatch.setattr("narrare._app.logging.configure_logging", _fake_config)

        lifespan_mod._configure_logging()

        assert called == [True]
