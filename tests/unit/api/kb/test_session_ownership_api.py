"""S7 — IDOR regression tests: ownership gate on KB creation sessions (HTTP).

Router-level matrix over all 8 KB-session endpoints (create, get, patch,
suggest, interview, enhance, complete, delete). Before the S7 fix the
routers never threaded identity into the service, so every endpoint
resolved access by bare ``session_id`` (or ``novel_id`` at create) —
cross-tenant read/write/delete/AI-ops, with ``complete`` persisting KB
entries under the victim's ``user_id``.

After the fix (plan S7): the owner's responses are unchanged
(200/201/204); a foreign caller gets 404 on every endpoint with zero
side effects (no session row, no store write, no AI call, no KB entry);
unknown ids are shape-identical to foreign ones (anti-enumeration).

The service-level matrix lives in ``test_session_ownership.py``
(RULE-04 split).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient, Response

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.kb.dependencies import get_kb_session_service

from ._test_fakes import make_owned_session, make_ownership_service

if TYPE_CHECKING:
    from fastapi import FastAPI

    from narrare.kb.session_models import KBCreationSession

    from ._test_fakes import (
        CountingAssistService,
        CountingSessionStore,
        FakeKBService,
    )

USER_A = uuid4()  # rightful owner of the novel + sessions (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A

SESSION_NOT_FOUND = "KB creation session"

_SESSION_URL = "/api/v1/novels/{novel_id}/kb/sessions/{session_id}"

_ENDPOINTS: dict[str, tuple[str, str]] = {
    "create": ("POST", "/api/v1/novels/{novel_id}/kb/sessions"),
    "get": ("GET", _SESSION_URL),
    "answer_field": ("PATCH", _SESSION_URL + "/fields/name"),
    "request_suggestion": ("POST", _SESSION_URL + "/suggest/name"),
    "request_interview_question": ("POST", _SESSION_URL + "/interview"),
    "request_enhancement": ("POST", _SESSION_URL + "/enhance"),
    "complete_session": ("POST", _SESSION_URL + "/complete"),
    "abandon_session": ("DELETE", _SESSION_URL),
}

_OWNER_STATUS = {
    "create": status.HTTP_201_CREATED,
    "abandon_session": status.HTTP_204_NO_CONTENT,
}

_JSON_BODIES: dict[str, dict[str, str] | None] = {
    "create": {"entity_type": "character"},
    "answer_field": {"value": "Aria"},
}


@pytest.fixture
def app():
    """Test app with overridden auth and rate limiter.

    The session service dependency is overridden per-test (see
    ``_install_service``), which replaces its whole subtree — no DB
    session is ever resolved.
    """
    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    async def _no_rate_limit() -> None:
        return None

    application.state.auth_user = str(USER_A)
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


def _install_service(
    app: FastAPI, ownership: dict[UUID, UUID]
) -> tuple[object, CountingSessionStore, CountingAssistService, FakeKBService]:
    service, store, assist, kb, _ = make_ownership_service(ownership)
    app.dependency_overrides[get_kb_session_service] = lambda: service
    return service, store, assist, kb


def _as_user(app: FastAPI, user_id: UUID) -> None:
    app.state.auth_user = str(user_id)


async def _call(
    client: AsyncClient,
    verb: str,
    *,
    novel_id: UUID,
    session_id: UUID | None = None,
) -> Response:
    method, template = _ENDPOINTS[verb]
    url = template.format(novel_id=novel_id, session_id=session_id or uuid4())
    return await client.request(method, url, json=_JSON_BODIES.get(verb))


class TestRouterOwnershipMatrix:
    """All 8 endpoints: owner unchanged; foreign/unknown → 404, no effects."""

    def _seed(
        self, app: FastAPI
    ) -> tuple[CountingSessionStore, CountingAssistService, FakeKBService, KBCreationSession]:
        _, store, assist, kb = _install_service(app, {NOVEL_ID: USER_A})
        session = make_owned_session(NOVEL_ID, USER_A)
        return store, assist, kb, session

    @pytest.mark.parametrize("verb", sorted(_ENDPOINTS))
    async def test_owner_flow_succeeds(self, app, client, verb: str) -> None:
        """Matrix case (1): owner gets 200/201/204 — behavior unchanged."""
        store, _assist, kb, session = self._seed(app)
        await store.create(session)

        response = await _call(client, verb, novel_id=NOVEL_ID, session_id=session.id)

        assert response.status_code == _OWNER_STATUS.get(verb, status.HTTP_200_OK)
        # Seeded row + (for create) exactly the one new row — nothing else.
        assert len(store.create_calls) == (2 if verb == "create" else 1)
        if verb == "complete_session":
            assert kb.created_entries is not None and len(kb.created_entries) == 1

    @pytest.mark.parametrize("verb", sorted(_ENDPOINTS))
    async def test_foreign_user_gets_404_without_side_effects(self, app, client, verb: str) -> None:
        """Matrix case (2)+(4): USER_B → 404 on every endpoint, zero effects."""
        store, assist, kb, session = self._seed(app)
        await store.create(session)
        _as_user(app, USER_B)
        rows_before = list(store.create_calls)

        response = await _call(client, verb, novel_id=NOVEL_ID, session_id=session.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        if verb == "create":
            assert store.create_calls == rows_before  # no session row for foreign novel
        elif verb == "get":
            # Router None-check path (plain HTTPException body).
            assert response.json() == {"detail": "Session not found"}
        else:
            assert response.json()["code"] == "NOT_FOUND"
        assert store.update_calls == []
        assert store.delete_calls == []
        assert assist.ai_calls == 0
        assert kb.created_entries == []

    @pytest.mark.parametrize("verb", [v for v in sorted(_ENDPOINTS) if v != "create"])
    async def test_unknown_session_404_shape_matches_foreign(self, app, client, verb: str) -> None:
        """Matrix case (3): unknown ≡ foreign — identical 404 shape, only the
        caller-supplied id differs."""
        store, _, _, session = self._seed(app)
        await store.create(session)
        _as_user(app, USER_B)
        unknown_id = uuid4()

        foreign = await _call(client, verb, novel_id=NOVEL_ID, session_id=session.id)
        unknown = await _call(client, verb, novel_id=NOVEL_ID, session_id=unknown_id)

        assert foreign.status_code == unknown.status_code == status.HTTP_404_NOT_FOUND
        if verb == "get":
            # Router None-check path: byte-identical bodies (no id echoed).
            assert foreign.content == unknown.content
        else:
            assert foreign.json() == {
                "detail": f"{SESSION_NOT_FOUND} ({session.id}) not found",
                "code": "NOT_FOUND",
            }
            assert unknown.json() == {
                "detail": f"{SESSION_NOT_FOUND} ({unknown_id}) not found",
                "code": "NOT_FOUND",
            }

    async def test_create_unknown_novel_404_shape_matches_foreign(self, app, client) -> None:
        """Create: unknown novel ≡ foreign novel (anti-enumeration)."""
        _install_service(app, {NOVEL_ID: USER_A})
        _as_user(app, USER_B)
        unknown_novel = uuid4()

        foreign = await _call(client, "create", novel_id=NOVEL_ID)
        unknown = await _call(client, "create", novel_id=unknown_novel)

        assert foreign.status_code == unknown.status_code == status.HTTP_404_NOT_FOUND
        assert foreign.json() == {"detail": f"Novel ({NOVEL_ID}) not found", "code": "NOT_FOUND"}
        assert unknown.json() == {
            "detail": f"Novel ({unknown_novel}) not found",
            "code": "NOT_FOUND",
        }
