"""Shared fixtures for the KB integration tests.

Single source of truth for the helpers that both
``test_kb_sessions_api.py`` (lifecycle endpoints) and
``test_kb_sessions_assist_api.py`` (LLM-mediated assist endpoints)
previously carried as verbatim duplicates. ``kb_service`` also
encapsulates the dependency-override cleanup that used to be a manual
per-test try/finally obligation: the app fixture is session-scoped, so
a leftover override would leak into subsequent tests (order-dependent
flakiness under pytest-randomly). Old convention for reference:
tests/integration/analysis/test_analysis_api.py.

The service fake (``FakeKBSessionService``, real return-value shapes per
RULE-TEST-01) and the session factory live in ``_assist_fakes.py``; the
bulk-extraction (ADR-092) fixtures live in ``_bulk_extraction_helpers.py``
and are defined here so test modules need no fixture imports (a fixture
imported into a test module collides with same-named parameters — F811).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare.kb.bulk_extraction import registry
from narrare.kb.bulk_extraction.dependencies import get_bulk_dispatcher
from narrare.kb.dependencies import get_kb_session_service
from tests.integration.kb._assist_fakes import FakeKBSessionService
from tests.integration.kb._assist_fakes import make_session as _make_session
from tests.integration.kb._bulk_extraction_helpers import (
    NoopDispatcher,
    add_chapters,
    create_novel,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from uuid import UUID

    from fastapi import FastAPI
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.session_models import KBCreationSession


@pytest.fixture
def make_session() -> Callable[..., KBCreationSession]:
    """Return the ``KBCreationSession`` factory (keyword overrides allowed)."""
    return _make_session


@pytest.fixture
def mock_service() -> FakeKBSessionService:
    """``KBSessionService`` fake with happy-path defaults for every method."""
    return FakeKBSessionService()


@pytest.fixture
def kb_service(app: FastAPI, mock_service: FakeKBSessionService) -> Iterator[FakeKBSessionService]:
    """Wire ``mock_service`` in as the ``get_kb_session_service`` override.

    The override is popped on teardown — guaranteed cleanup on the
    session-scoped app, no per-test try/finally needed. Tests customize
    behavior by overriding individual methods on the returned fake
    (e.g. ``kb_service.get_session = AsyncMock(return_value=None)``)
    before issuing the request; the override lambda closes over the same
    object.
    """
    app.dependency_overrides[get_kb_session_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.pop(get_kb_session_service, None)


# ---------------------------------------------------------------------------
# Bulk extraction (ADR-092) — see _bulk_extraction_helpers.py
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_bulk_registry() -> Iterator[None]:
    """Empty the process-global bulk registry around each requesting test.

    Opt-in (``pytestmark = pytest.mark.usefixtures("clean_bulk_registry")``)
    so the sweep stays scoped to the bulk-extraction suite instead of
    running under every KB test.
    """
    registry._JOBS.clear()
    yield
    registry._JOBS.clear()


@pytest.fixture
def bulk_dispatcher(app: FastAPI) -> Iterator[NoopDispatcher]:
    """No-op dispatcher wired through the DI seam; popped on teardown."""
    dispatcher = NoopDispatcher()
    app.dependency_overrides[get_bulk_dispatcher] = lambda: dispatcher
    yield dispatcher
    app.dependency_overrides.pop(get_bulk_dispatcher, None)


@pytest.fixture
async def bulk_novel_id(
    client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
) -> UUID:
    """A novel owned by the authenticated user."""
    return await create_novel(client, auth_headers, "Bulk Extraction Novel")


@pytest.fixture
async def bulk_chapter_ids(db_session: AsyncSession, bulk_novel_id: UUID) -> list[UUID]:
    """Three contentful chapters of ``bulk_novel_id`` (position order)."""
    return await add_chapters(db_session, bulk_novel_id)
