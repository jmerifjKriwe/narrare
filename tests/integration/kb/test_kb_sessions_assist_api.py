"""Integration tests for the KB session AI-assist endpoints.

Covers the LLM-mediated session operations: request_suggestion,
request_interview_question, request_enhancement. The lifecycle endpoints
(create, get, answer_field, complete, stream, abandon) live in
``test_kb_sessions_api.py``. Mocks KBSessionService via dependency_overrides.
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
    from fastapi import FastAPI
    from httpx import AsyncClient


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


def _override(app: FastAPI, svc: MagicMock) -> None:
    """Wire the mock service into the app's dependency overrides.

    Callers must pop the override in a ``finally`` block — the app fixture
    is session-scoped, so a leftover override leaks into subsequent tests
    (order-dependent flakiness under pytest-randomly). Cleanup convention:
    tests/integration/analysis/test_analysis_api.py.
    """
    app.dependency_overrides[get_kb_session_service] = lambda: svc


@pytest.fixture
def mock_service() -> MagicMock:
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


class TestRequestSuggestion:
    async def test_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/suggest/name", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert data["suggestion"]["field_key"] == "name"
        assert data["suggestion"]["suggestion"] == "Aria"

    async def test_returns_401_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/suggest/name")
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 401

    async def test_returns_422_invalid_uuid(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(
                "/api/v1/novels/not-a-uuid/kb/sessions/not-a-uuid/suggest/name",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 422


class TestRequestInterviewQuestion:
    async def test_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/interview", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert data["question"]["field_key"] == "personality"

    async def test_returns_401_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/interview")
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 401


class TestRequestEnhancement:
    async def test_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/enhance", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert "enhancement" in data
        assert "draft_entry" in data["enhancement"]
        assert "progress" in data["enhancement"]

    async def test_returns_401_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/enhance")
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 401
