"""Unit tests for ``narrare._app.logging`` — configure_logging.

Tests both development (dual-handler) and production (JSON stdout) logging
configuration paths with fake settings.

Uses ``monkeypatch`` to inject controlled Settings and ``tmp_path`` for log
files so no real filesystem side-effects remain.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import Any

import pytest
import structlog

import narrare._app.logging as logging_mod
from narrare._app.logging import (
    _configure_development_logging,
    _configure_production_logging,
    configure_logging,
)

# ---------------------------------------------------------------------------
# Fake settings
# ---------------------------------------------------------------------------


class _FakeSettings:
    """Minimal settings object for logging configuration tests."""

    def __init__(
        self,
        *,
        environment: str = "development",
        log_level: str = "INFO",
        log_file: str | None = None,
    ) -> None:
        self.environment = environment
        self.log_level = log_level
        self.log_file = log_file

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Any:  # pyright: ignore[reportUnusedFunction]
    """Save and restore root logger handlers and structlog config between tests."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    # Snapshot structlog's global config. The processors list MUST be a copy,
    # not a reference: ``configure_logging()`` replaces the configured list
    # (leaking ``cache_logger_on_first_use=True`` and a stale list identity
    # into other test files otherwise), and structlog's ``capture_logs``
    # mutates the configured list in place — either way a snapshot held by
    # reference would be corrupted. Processor instances stay shared by
    # identity; only the list object is copied.
    saved_structlog = structlog.get_config()
    saved_structlog["processors"] = list(saved_structlog["processors"])
    yield
    for handler in root.handlers[:]:
        handler.close()
    root.handlers[:] = saved_handlers
    root.level = saved_level
    structlog.configure(**saved_structlog)


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: _FakeSettings,
) -> None:
    """Patch ``get_settings`` in the logging module's import scope."""

    def _fake_get_settings() -> _FakeSettings:
        return settings

    monkeypatch.setattr(
        "narrare._app.config.get_settings",
        _fake_get_settings,
    )


# ---------------------------------------------------------------------------
# configure_logging — routing
# ---------------------------------------------------------------------------


class TestConfigureLoggingRouting:
    def test_dev_with_log_file_routes_to_development(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any,
    ) -> None:
        log_file = str(tmp_path / "dev.log")
        settings = _FakeSettings(environment="development", log_file=log_file)
        _patch_settings(monkeypatch, settings)

        called: dict[str, bool] = {"dev": False}

        original = _configure_development_logging

        def _spy_dev(*args: Any, **kwargs: Any) -> None:
            called["dev"] = True
            original(*args, **kwargs)

        monkeypatch.setattr(logging_mod, "_configure_development_logging", _spy_dev)
        configure_logging()
        assert called["dev"] is True

    def test_prod_routes_to_production(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _FakeSettings(environment="production", log_file=None)
        _patch_settings(monkeypatch, settings)

        called: dict[str, bool] = {"prod": False}

        def _spy_prod(*args: Any, **kwargs: Any) -> None:
            called["prod"] = True

        monkeypatch.setattr(logging_mod, "_configure_production_logging", _spy_prod)
        configure_logging()
        assert called["prod"] is True

    def test_dev_without_log_file_routes_to_production(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Development without a log_file falls through to production logging."""
        settings = _FakeSettings(environment="development", log_file=None)
        _patch_settings(monkeypatch, settings)

        called: dict[str, bool] = {"prod": False}

        def _spy_prod(*args: Any, **kwargs: Any) -> None:
            called["prod"] = True

        monkeypatch.setattr(logging_mod, "_configure_production_logging", _spy_prod)
        configure_logging()
        assert called["prod"] is True


# ---------------------------------------------------------------------------
# _configure_development_logging
# ---------------------------------------------------------------------------


class TestDevelopmentLogging:
    def test_creates_console_file_and_error_handlers(
        self,
        tmp_path: Any,
    ) -> None:
        log_file = str(tmp_path / "app.log")
        shared: list[Any] = []

        _configure_development_logging(shared, logging.DEBUG, log_file)

        root = logging.getLogger()
        # Should have: console handler, file handler, error file handler
        assert any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
            for h in root.handlers
        )
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 2  # regular file + error file
        assert root.level == logging.DEBUG

    def test_uvicorn_loggers_routed(
        self,
        tmp_path: Any,
    ) -> None:
        log_file = str(tmp_path / "app.log")
        shared: list[Any] = []

        _configure_development_logging(shared, logging.DEBUG, log_file)

        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            uv_logger = logging.getLogger(name)
            assert len(uv_logger.handlers) == 2  # console + file
            assert uv_logger.propagate is False


# ---------------------------------------------------------------------------
# _configure_production_logging
# ---------------------------------------------------------------------------


class TestProductionLogging:
    def test_creates_stream_and_error_file_handlers(self, tmp_path: Any) -> None:
        shared: list[Any] = []

        # Change CWD so the "logs" directory is created in tmp
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            _configure_production_logging(shared, logging.INFO)
        finally:
            os.chdir(original_cwd)

        root = logging.getLogger()
        stream_handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert len(stream_handlers) >= 1
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1  # error file only
        assert root.level == logging.INFO
