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
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.kb.dependencies import get_kb_session_service
from narrare.kb.session_models import KBCreationField, KBCreationSession
from narrare.kb.session_service import KBSessionService

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from fastapi import FastAPI


def _make_session(**overrides: object) -> KBCreationSession:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "novel_id": uuid4(),
        "user_id": uuid4(),
        "entity_type": "character",
        "fields": [
            KBCreationField(field_key="name", label="Name", required=True),
            KBCreationField(field_key="personality", label="Personality"),
        ],
    }
    defaults.update(overrides)
    return KBCreationSession.model_validate(defaults)


@pytest.fixture
def make_session() -> Callable[..., KBCreationSession]:
    """Return the ``KBCreationSession`` factory (keyword overrides allowed)."""
    return _make_session


@pytest.fixture
def mock_service() -> MagicMock:
    """``KBSessionService`` mock with happy-path defaults for every method."""
    svc = MagicMock(spec=KBSessionService)
    svc.create_session = AsyncMock(return_value=_make_session())
    svc.get_session = AsyncMock(return_value=_make_session())
    svc.answer_field = AsyncMock(return_value=_make_session())
    svc.request_suggestion = AsyncMock(
        return_value=(
            _make_session(),
            {
                "field_key": "name",
                "suggestion": "Aria",
                "reasoning": "Fits genre",
                "context_used": [],
            },
        )
    )
    svc.request_interview_question = AsyncMock(
        return_value=(
            _make_session(),
            {
                "field_key": "personality",
                "question": "What drives this character?",
                "reasoning": "Core trait",
            },
        )
    )
    svc.request_enhancement = AsyncMock(
        return_value=(
            _make_session(),
            {
                "draft_entry": {"name": "Aria"},
                "progress": 0.5,
                "reasoning": "Good start",
                "context_used": [],
            },
        )
    )
    svc.complete_session = AsyncMock(return_value=(_make_session(status="complete"), uuid4()))
    svc.abandon_session = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def kb_service(app: FastAPI, mock_service: MagicMock) -> Iterator[MagicMock]:
    """Wire ``mock_service`` in as the ``get_kb_session_service`` override.

    The override is popped on teardown — guaranteed cleanup on the
    session-scoped app, no per-test try/finally needed. Tests customize
    behavior by mutating the returned mock (e.g. ``kb_service.get_session
    = AsyncMock(return_value=None)``) before issuing the request; the
    override lambda closes over the same object.
    """
    app.dependency_overrides[get_kb_session_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.pop(get_kb_session_service, None)
