"""Integration tests for the KB session lifecycle API endpoints.

Covers create, get, answer_field, complete, stream (not exposed), abandon;
the LLM-mediated assist endpoints (suggest, interview, enhance) live in
``test_kb_sessions_assist_api.py``. Mocks KBSessionService via the shared
``kb_service`` fixture (conftest.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import MagicMock

    from httpx import AsyncClient

    from narrare.kb.session_models import KBCreationSession


class TestCreateSession:
    async def test_returns_201(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/sessions",
            json={"entity_type": "character"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["entity_type"] == "character"
        assert "id" in data and data["status"] == "active"
        assert isinstance(data["fields"], list)
        kb_service.create_session.assert_awaited_once()

    async def test_returns_401_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/sessions", json={"entity_type": "character"}
        )
        assert resp.status_code == 401

    async def test_returns_422_empty_entity_type(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/sessions",
            json={"entity_type": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestGetSession:
    async def test_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.get(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "character"
        assert "id" in data and "fields" in data

    async def test_returns_401_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        resp = await client.get(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}")
        assert resp.status_code == 401

    async def test_returns_404_when_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        kb_service.get_session = AsyncMock(return_value=None)
        resp = await client.get(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404


class TestAnswerField:
    async def test_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
        make_session: Callable[..., KBCreationSession],
    ) -> None:
        session = make_session()
        session.fields[0].user_value = "Aria"
        session.fields[0].final_value = "Aria"
        kb_service.answer_field = AsyncMock(return_value=session)
        resp = await client.patch(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{session.id}/fields/name",
            json={"value": "Aria"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["fields"][0]["user_value"] == "Aria"

    async def test_returns_401_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        resp = await client.patch(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/fields/name",
            json={"value": "Aria"},
        )
        assert resp.status_code == 401

    async def test_returns_422_empty_value(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.patch(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/fields/name",
            json={"value": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestCompleteSession:
    async def test_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
        make_session: Callable[..., KBCreationSession],
    ) -> None:
        entry_id = uuid4()
        kb_service.complete_session = AsyncMock(
            return_value=(make_session(status="complete"), entry_id)
        )
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/complete", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["status"] == "complete"
        assert data["entry_id"] == str(entry_id)

    async def test_returns_401_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        resp = await client.post(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/complete")
        assert resp.status_code == 401


class TestStreamSession:
    async def test_stream_endpoint_is_not_exposed(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        """The unused session state stream is not part of the public API."""

        resp = await client.get(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/stream", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_stream_endpoint_is_not_exposed_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        """Missing auth does not matter because the route is not registered."""

        resp = await client.get(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}/stream")
        assert resp.status_code == 404


class TestAbandonSession:
    async def test_returns_204(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.delete(
            f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 204
        kb_service.abandon_session.assert_awaited_once()

    async def test_returns_401_without_auth(
        self, client: AsyncClient, kb_service: MagicMock
    ) -> None:
        resp = await client.delete(f"/api/v1/novels/{uuid4()}/kb/sessions/{uuid4()}")
        assert resp.status_code == 401

    async def test_returns_422_invalid_uuid(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        kb_service: MagicMock,
    ) -> None:
        resp = await client.delete(
            "/api/v1/novels/not-a-uuid/kb/sessions/not-a-uuid", headers=auth_headers
        )
        assert resp.status_code == 422
