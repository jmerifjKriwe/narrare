"""Shared fixtures for the KB session API integration tests.

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
RULE-TEST-01) and the session factory live in ``_assist_fakes.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare.kb.dependencies import get_kb_session_service
from tests.integration.kb._assist_fakes import FakeKBSessionService
from tests.integration.kb._assist_fakes import make_session as _make_session

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from fastapi import FastAPI

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
