# tests/unit/api/_app/_lifespan_helpers.py
"""Shared fakes + patch helpers for the ``_app.lifespan`` test modules.

Split out of ``test_lifespan.py`` (RULE-04): the core lifespan tests and
the budget-guard lifecycle tests drive the same fake settings/app and the
same heavy-dependency patch set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import narrare._app.lifespan as lifespan_mod

if TYPE_CHECKING:
    import pytest
    from fastapi import FastAPI


async def _noop_async() -> None:
    """Async no-op for patching."""


def _returning_async(value: int):
    """Return an async function that yields *value*."""

    async def _fn() -> int:
        return value

    return _fn


async def _no_budget_settings(user_id: object) -> object:
    """Async stand-in row for ``UserAiSettingsRepository.get`` (no budget)."""
    del user_id

    class _Row:
        monthly_budget_usd: object = None
        budget_mode: str = "warn"

    return _Row()


class _FakeSettings:
    """Minimal settings stand-in for lifespan testing."""

    def __init__(
        self,
        *,
        is_test: bool = True,
    ) -> None:
        self.is_test = is_test


class _FakeState:
    """Simple namespace for ``app.state``."""

    wiki_event_publisher: Any = None


class _FakeApp:
    """Minimal FastAPI app substitute."""

    def __init__(self) -> None:
        self.state = _FakeState()


def _make_app() -> FastAPI:
    """Create a fake app, cast for lifespan signature compatibility."""
    return cast("FastAPI", _FakeApp())


def _patch_common(monkeypatch: pytest.MonkeyPatch, settings: _FakeSettings) -> None:
    """Patch heavy dependencies shared by every lifespan test."""

    # Logging configuration — avoid reconfiguring structlog during tests.
    monkeypatch.setattr(lifespan_mod, "_configure_logging", lambda: None)

    # Settings — return our fake instead of real Settings().
    monkeypatch.setattr("narrare._app.config.get_settings", lambda: settings)

    # Wiki listener builder — avoid DB and heavy imports inside lifespan.
    async def _fake_build_wiki() -> None:
        return None

    def _fake_make_factory(_svc: Any) -> Any:
        return lambda *_a, **_kw: None

    monkeypatch.setattr("narrare.wiki.dependencies.build_core_wiki_service", _fake_build_wiki)
    monkeypatch.setattr("narrare.wiki.dependencies.make_system_wiki_factory", _fake_make_factory)
