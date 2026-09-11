"""Integration tests for the KB session lifecycle API endpoints.

Covers create, get, answer_field, complete, stream (not exposed), abandon;
the LLM-mediated assist endpoints (suggest, interview, enhance) live in
``test_kb_sessions_assist_api.py``. Mocks KBSessionService via
dependency_overrides.
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


class TestCreateSession:
    async def test_returns_201(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(
                f"/api/v1/novels/{uuid4()}/kb/sessions",
                json={"entity_type": "character"},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 201
        data = resp.json()
        assert data["entity_type"] == "character"
        assert "id" in data and data["status"] == "active"
        assert isinstance(data["fields"], list)
        mock_service.create_session.assert_awaited_once()

    async def test_returns_401_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(
                f"/api/v1/novels/{uuid4()}/kb/sessions", json={"entity_type": "character"}
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 401

    async def test_returns_422_empty_entity_type(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(
                f"/api/v1/novels/{uuid4()}/kb/sessions",
                json={"entity_type": ""},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 422


class TestGetSession:
    async def test_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.get(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "character"
        assert "id" in data and "fields" in data

    async def test_returns_401_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.get(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}")
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 401

    async def test_returns_404_when_not_found(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        mock_service.get_session = AsyncMock(return_value=None)
        _override(app, mock_service)
        try:
            resp = await client.get(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 404


class TestAnswerField:
    async def test_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        session = _make_session()
        session.fields[0].user_value = "Aria"
        session.fields[0].final_value = "Aria"
        mock_service.answer_field = AsyncMock(return_value=session)
        _override(app, mock_service)
        try:
            resp = await client.patch(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{session.id}/fields/name",
                json={"value": "Aria"},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 200
        assert resp.json()["fields"][0]["user_value"] == "Aria"

    async def test_returns_401_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.patch(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/fields/name",
                json={"value": "Aria"},
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 401

    async def test_returns_422_empty_value(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.patch(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/fields/name",
                json={"value": ""},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 422


class TestCompleteSession:
    async def test_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        entry_id = uuid4()
        mock_service.complete_session = AsyncMock(
            return_value=(_make_session(status="complete"), entry_id)
        )
        _override(app, mock_service)
        try:
            resp = await client.post(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/complete", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["status"] == "complete"
        assert data["entry_id"] == str(entry_id)

    async def test_returns_401_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.post(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/complete")
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 401


class TestStreamSession:
    async def test_stream_endpoint_is_not_exposed(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        """The unused session state stream is not part of the public API."""

        _override(app, mock_service)
        try:
            resp = await client.get(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/stream", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 404

    async def test_stream_endpoint_is_not_exposed_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        """Missing auth does not matter because the route is not registered."""

        _override(app, mock_service)
        try:
            resp = await client.get(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/stream")
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 404


class TestAbandonSession:
    async def test_returns_204(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_service: MagicMock,
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.delete(
                f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 204
        mock_service.abandon_session.assert_awaited_once()

    async def test_returns_401_without_auth(
        self, client: AsyncClient, app: FastAPI, mock_service: MagicMock
    ) -> None:
        _override(app, mock_service)
        try:
            resp = await client.delete(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}")
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
            resp = await client.delete(
                "/api/v1/novels/not-a-uuid/kb/sessions/not-a-uuid", headers=auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_kb_session_service, None)
        assert resp.status_code == 422
