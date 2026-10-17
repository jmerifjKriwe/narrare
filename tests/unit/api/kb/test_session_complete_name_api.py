"""F9-1 — the complete route accepts an optional body ``name`` (HTTP).

Regression context: assisted creation could never complete — the FE
collects the entry name, but the complete route accepted no body, so
``complete_session`` always raised "Session must have a name before
completion" (→ 400). Now an optional ``{"name": ...}`` body fills the
session name before mapping; an absent body or absent name keeps the
honest 400 guard.

Integration-style unit tests: real FastAPI app + real ``KBSessionService``
over in-memory fakes (pattern from ``test_session_ownership_api.py``).
Service-level coverage of the ``name`` parameter lives in
``test_session_service_complete.py`` (RULE-04 split).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.kb.dependencies import get_kb_session_service

from ._test_fakes import make_owned_session, make_ownership_service

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import Response

    from ._test_fakes import CountingSessionStore, FakeKBService

USER = uuid4()
NOVEL_ID = uuid4()

_URL = "/api/v1/novels/{novel_id}/kb/sessions/{session_id}/complete"


@pytest.fixture
def app():
    """Test app with overridden auth and rate limiter.

    The session service dependency is overridden per-test (``_seed``)
    with the REAL service over fakes — no DB session is ever resolved.
    """
    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    async def _no_rate_limit() -> None:
        return None

    application.state.auth_user = str(USER)
    application.dependency_overrides[get_current_user_id] = _mock_auth
    application.dependency_overrides[AI_ANALYSIS_LIMITER] = _no_rate_limit
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


def _seed(app: FastAPI) -> tuple[CountingSessionStore, FakeKBService]:
    """Install the real service (fakes underneath) and return its fakes."""
    service, store, _assist, kb, _repo = make_ownership_service({NOVEL_ID: USER})
    app.dependency_overrides[get_kb_session_service] = lambda: service
    return store, kb


async def _complete(
    client: AsyncClient, session_id: object, *, json: dict[str, str] | None = None
) -> Response:
    return await client.post(_URL.format(novel_id=NOVEL_ID, session_id=session_id), json=json)


class TestCompleteSessionName:
    """F9-1: optional body name on POST .../complete."""

    async def test_body_name_creates_entry_with_name(self, app, client) -> None:
        """Unnamed session + complete WITH body name → 200, entry carries it."""
        store, kb = _seed(app)
        session = make_owned_session(NOVEL_ID, USER, name=None)
        await store.create(session)

        response = await _complete(client, session.id, json={"name": "Aria"})

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["name"] == "Aria"
        assert data["session"]["status"] == "complete"
        assert kb.created_entries is not None
        assert len(kb.created_entries) == 1
        entry_data = kb.created_entries[0]["data"]
        assert getattr(entry_data, "name", None) == "Aria"

    async def test_no_body_returns_400_for_unnamed_session(self, app, client) -> None:
        """Absent body → honest guard stays: 400, no entry created."""
        store, kb = _seed(app)
        session = make_owned_session(NOVEL_ID, USER, name=None)
        await store.create(session)

        response = await _complete(client, session.id)

        assert response.status_code == 400
        assert "Session must have a name" in response.json()["detail"]
        assert kb.created_entries == []

    async def test_body_without_name_returns_400_for_unnamed_session(self, app, client) -> None:
        """``{}`` body (name absent) → same honest guard: 400."""
        store, kb = _seed(app)
        session = make_owned_session(NOVEL_ID, USER, name=None)
        await store.create(session)

        response = await _complete(client, session.id, json={})

        assert response.status_code == 400
        assert "Session must have a name" in response.json()["detail"]
        assert kb.created_entries == []

    async def test_blank_name_is_rejected_422(self, app, client) -> None:
        """Explicit blank name → 422 (mirrors KBEntryCreate name constraints)."""
        store, _kb = _seed(app)
        session = make_owned_session(NOVEL_ID, USER, name=None)
        await store.create(session)

        response = await _complete(client, session.id, json={"name": ""})

        assert response.status_code == 422

    async def test_named_session_completes_without_body(self, app, client) -> None:
        """Session that already has a name completes as before (no body)."""
        store, kb = _seed(app)
        session = make_owned_session(NOVEL_ID, USER, name="Aria")
        await store.create(session)

        response = await _complete(client, session.id)

        assert response.status_code == 200
        assert response.json()["entry_id"]
        assert kb.created_entries is not None and len(kb.created_entries) == 1
