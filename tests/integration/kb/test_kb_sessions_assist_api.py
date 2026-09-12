"""Integration tests for the KB session AI-assist endpoints.

Covers the LLM-mediated session operations: request_suggestion,
request_interview_question, request_enhancement. The lifecycle endpoints
(create, get, answer_field, complete, stream, abandon) live in
``test_kb_sessions_api.py``. Mocks KBSessionService via the shared
``kb_service`` fixture (conftest.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from httpx import AsyncClient


class TestRequestSuggestion:
    async def test_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/suggest/name", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert data["suggestion"]["field_key"] == "name"
        assert data["suggestion"]["suggestion"] == "Aria"

    async def test_returns_401_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        resp = await client.post(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/suggest/name")
        assert resp.status_code == 401

    async def test_returns_422_invalid_uuid(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.post(
            "/api/v1/novels/not-a-uuid/kb/sessions/not-a-uuid/suggest/name",
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestRequestInterviewQuestion:
    async def test_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/interview", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert data["question"]["field_key"] == "personality"

    async def test_returns_401_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        resp = await client.post(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/interview")
        assert resp.status_code == 401


class TestRequestEnhancement:
    async def test_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/enhance", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert "enhancement" in data
        assert "draft_entry" in data["enhancement"]
        assert "progress" in data["enhancement"]

    async def test_returns_401_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        resp = await client.post(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/enhance")
        assert resp.status_code == 401
