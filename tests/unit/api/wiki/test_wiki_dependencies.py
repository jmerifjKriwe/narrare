"""Unit tests for wiki/dependencies.py — DI factory functions.

Tests the session-to-repository wiring and the system-mode factory
closure.  ``build_core_wiki_service()`` and ``get_wiki_service()``
are skipped per testing strategy (covered by router/integration tests).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.wiki.dependencies import get_wiki_repository, make_system_wiki_factory
from narrare.wiki.repository import WikiRepository
from narrare.wiki.service import APIWikiService
from tests.fakes.fake_core_wiki_service import FakeCoreWikiService


class TestGetWikiRepository:
    """get_wiki_repository(session) — creates WikiRepository."""

    def test_returns_wiki_repository(self) -> None:
        """Returns WikiRepository wrapping the given session."""
        mock_session = AsyncMock(spec=AsyncSession)
        repo = get_wiki_repository(mock_session)
        assert isinstance(repo, WikiRepository)
        assert repo._session is mock_session


class TestMakeSystemWikiFactory:
    """make_system_wiki_factory(core_service) — system-mode factory closure."""

    def test_factory_creates_system_service(self) -> None:
        """Factory closure creates APIWikiService with system_mode=True."""
        core_service = FakeCoreWikiService()
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("narrare._app.database._async_session_factory", return_value=mock_session):
            factory_fn = make_system_wiki_factory(core_service)
            svc = factory_fn()

        assert isinstance(svc, APIWikiService)
        assert svc._system_mode is True

    def test_factory_uses_captured_core_service(self) -> None:
        """Factory uses the same core_service passed to make_system_wiki_factory."""
        core_service = FakeCoreWikiService()
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("narrare._app.database._async_session_factory", return_value=mock_session):
            factory_fn = make_system_wiki_factory(core_service)
            svc = factory_fn()

        assert svc._core is core_service

    def test_factory_creates_fresh_service_per_call(self) -> None:
        """Each factory call creates a new APIWikiService instance."""
        core_service = FakeCoreWikiService()
        mock_session_1 = AsyncMock(spec=AsyncSession)
        mock_session_2 = AsyncMock(spec=AsyncSession)

        with patch(
            "narrare._app.database._async_session_factory",
            side_effect=[mock_session_1, mock_session_2],
        ):
            factory_fn = make_system_wiki_factory(core_service)
            svc_1 = factory_fn()
            svc_2 = factory_fn()

        assert svc_1 is not svc_2
