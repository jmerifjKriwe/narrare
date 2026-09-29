"""Integration suite for the CHAT ask endpoint (ADR-086 #7b gap).

Covers POST /api/v1/chat end-to-end on the REAL ``get_chat_service``
factory (no DI override) — the lazy per-user CHAT cascade resolves at
first use inside ``ask()`` (ADR-086 L12), so the suite seeds cascade
state instead of patching the factory:

- happy path — seeded provider (routing cascade resolves) → 200 SSE
  stream; the LLM boundary is faked at its two seams: the registry via
  the canonical ``FakeModelRegistry`` at the factory-import site
  (``narrare.chat.dependencies.get_model_registry`` — the real registry
  would reject the seeded synthetic provider name) and the agent via
  ``narrare_core.chat.chat_agent.ChatAgent`` (the unit-suite convention —
  ADR-030 fake at the domain boundary, no real LLM call). Asserts the
  meta/token/done SSE frames AND persistence (user + assistant rows);
- 401 unauthenticated;
- ownership 404 — foreign project (novel owned by a second user) → 404
  even though the caller has NO provider configuration: the service's
  project-ownership gate fires BEFORE the first-use resolution
  (gate-before-resolution). This 404-before-400 ordering is the L12
  sanctioned delta — pinned explicitly: a 400 here would mean the
  cascade resolved ahead of the gate. Unlike the summary router, the
  chat router does NOT convert the service's ``NotFoundError``, so the
  body carries the app-level ``NarrareError`` handler shape (``detail``
  + ``code``) and the error surfaces pre-header (no
  ``text/event-stream``), never as a broken SSE stream.

The remaining two suite nodes live in the L12 sibling
``tests/integration/chat/test_chat_lazy_resolution.py`` (kept, not
duplicated): 422 invalid body (validation wins over 400 — the lazy
factory does no cascade work at construction) and the loud pre-header
400 for an unconfigured provider (no ``text/event-stream`` header).

Mirrors ``tests/integration/writing/test_summary_api.py`` (ADR-086 #7a
convention).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

_CHAT_URL = "/api/v1/chat"


async def _current_user_id(auth_headers: dict[str, str]) -> str:
    """Extract the authenticated user's id from the fixture JWT."""
    from narrare._app.config import get_settings
    from narrare.auth.security import verify_access_token

    token = auth_headers["Authorization"].removeprefix("Bearer ")
    payload = verify_access_token(token, get_settings().secret_key)
    assert payload is not None, "auth_headers fixture produced an invalid token"
    return str(payload["sub"])


async def _seed_default_provider(db_session: AsyncSession, user_id: str) -> None:
    """Seed an active default provider so the routing cascade resolves.

    Minimal cascade-sufficient state (ModelRoutingResolverImpl step 5,
    ``user_default`` source): one active ``UserProvider`` row plus a
    ``UserAiSettings`` row pointing ``default_provider_id`` /
    ``default_model`` at it. ``api_key_encrypted`` stays empty — the
    resolver maps that to ``api_key=None`` (no crypto needed).
    """
    import uuid

    from narrare.settings.models import UserAiSettings, UserProvider

    provider = UserProvider(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        provider_name="test",
        api_key_encrypted="",
    )
    db_session.add(provider)
    await db_session.flush()

    db_session.add(
        UserAiSettings(
            user_id=uuid.UUID(user_id),
            default_provider_id=provider.id,
            default_model="test-model",
        )
    )
    await db_session.flush()


def _parse_sse_frames(text: str) -> list[tuple[str, dict[str, object]]]:
    """Split a raw SSE body into ``(event_type, json_data)`` frames."""
    frames: list[tuple[str, dict[str, object]]] = []
    for raw in text.split("\n\n"):
        if not raw.strip():
            continue
        lines = raw.split("\n")
        event_type = lines[0].removeprefix("event: ")
        data = json.loads(lines[1].removeprefix("data: "))
        frames.append((event_type, data))
    return frames


def _fake_chat_agent() -> MagicMock:
    """ChatAgent stand-in streaming two tokens + done (unit-suite pattern).

    The real agent rejects the ``TestModel`` the fake registry prepares,
    so the domain boundary is faked per ADR-030 — same shape as the
    ``ChatAgent`` mocks in ``tests/unit/api/chat/``.
    """
    from narrare_core.agents.base import StreamEvent
    from narrare_core.chat.chat_agent import ChatAgent

    async def _stream(*args: object, **kwargs: object) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(type="token", text="Greetings, ")
        yield StreamEvent(type="token", text="traveller!")
        yield StreamEvent(
            type="done",
            text="Greetings, traveller!",
            usage={"total_tokens": 21},
            new_messages=[],
        )

    agent = MagicMock(name="chat_api_agent", spec=ChatAgent)
    agent.run_stream = _stream
    return agent


class TestChatApiIntegration:
    """Real-factory contract of POST /api/v1/chat (SSE streaming)."""

    async def test_chat_with_seeded_provider_streams_sse_and_persists_turn(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        """Seeded cascade → 200 SSE stream + persisted user/assistant rows.

        The REAL factory wires the lazy CHAT cascade; the seeded provider
        resolves at first use inside ``ask()``; the faked agent streams
        two tokens + done through the real SSE bridge; the real
        ``SQLAlchemyConversationStore`` persists both rows. Project-less
        request → project tiers skipped (NOTES-001 §6b); the KB bundle
        degrades to empty (RULE-11, no KB rows).
        """
        from uuid import UUID

        from sqlalchemy import select

        from narrare.chat.models import ChatConversation, ChatMessage
        from narrare_core.llm import LLMIntent
        from tests.fakes.fake_llm_gateway import FakeModelRegistry

        user_id = await _current_user_id(auth_headers)
        await _seed_default_provider(db_session, user_id)

        registry = FakeModelRegistry()
        with (
            patch(
                "narrare.chat.dependencies.get_model_registry",
                return_value=registry,
            ),
            patch(
                "narrare_core.chat.chat_agent.ChatAgent",
                return_value=_fake_chat_agent(),
            ),
        ):
            response = await client.post(
                _CHAT_URL,
                json={"message": "Who are you?"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        frames = _parse_sse_frames(response.text)
        assert [event_type for event_type, _ in frames] == [
            "meta",
            "token",
            "token",
            "done",
        ]
        meta = frames[0][1]
        conv_id = UUID(str(meta["conversation_id"]))
        assert str(meta["request_id"])
        assert frames[1][1]["text"] == "Greetings, "
        assert frames[2][1]["text"] == "traveller!"
        assert frames[3][1]["usage"] == {"total_tokens": 21}

        # Wiring evidence: the first-use resolve reached the registry's
        # prepare() assembly point with the seeded provider/model ids and
        # the CHAT intent.
        assert len(registry.prepare_calls) == 1
        prepare = registry.prepare_calls[0]
        assert prepare["intent"] == LLMIntent.CHAT
        config = prepare["config"]
        assert config is not None
        assert config.provider_name == "test"
        assert config.model_id == "test-model"

        # Persistence: conversation row + user message + assistant response.
        # (Set assertion: both rows share the transaction's now() timestamp,
        # so created_at ordering is not deterministic within the turn.)
        conversation = await db_session.scalar(
            select(ChatConversation).where(ChatConversation.id == conv_id)
        )
        assert conversation is not None
        assert conversation.project_id is None
        assert str(conversation.user_id) == user_id
        rows = (
            (
                await db_session.execute(
                    select(ChatMessage).where(ChatMessage.conversation_id == conv_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert {(row.role, row.content) for row in rows} == {
            ("user", "Who are you?"),
            ("assistant", "Greetings, traveller!"),
        }

    async def test_chat_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """No Authorization header → 401 before any service work."""
        response = await client.post(_CHAT_URL, json={"message": "Who are you?"})
        assert response.status_code == 401

    async def test_chat_foreign_project_returns_404_before_resolution(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        """Foreign project → 404 even with the caller's provider unseeded.

        The project-ownership gate precedes the first-use resolution: a
        400 (NO_AI_PROVIDER) here would mean the cascade resolved ahead
        of the gate. This 404-before-400 ordering is the ADR-086 L12
        sanctioned delta — pinned explicitly (foreign ≡ unknown,
        anti-enumeration). The error surfaces pre-header — a 200 SSE
        response with a mid-stream failure would violate the
        await-before-StreamingResponse contract.
        """
        import uuid
        from datetime import UTC, datetime

        from narrare._app.config import get_settings
        from narrare.auth.models import User
        from narrare.auth.security import create_access_token

        now = datetime.now(UTC)
        owner = User(
            id=uuid.uuid4(),
            email=f"chat-owner-{uuid.uuid4().hex[:12]}@example.com",
            hashed_password="not-a-real-hash",
            created_at=now,
            updated_at=now,
        )
        db_session.add(owner)
        await db_session.flush()
        owner_headers = {
            "Authorization": "Bearer "
            + create_access_token(
                subject=str(owner.id),
                secret_key=get_settings().secret_key,
                expires_minutes=get_settings().access_token_expire_minutes,
            )
        }

        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "Chat Foreign Novel", "language": "en"},
            headers=owner_headers,
        )
        assert novel_resp.status_code == 201
        foreign_novel_id = novel_resp.json()["id"]

        response = await client.post(
            _CHAT_URL,
            json={"message": "Who are you?", "project_id": foreign_novel_id},
            headers=auth_headers,
        )

        assert response.status_code == 404
        body = response.json()
        # Chat does NOT convert the error in the router (unlike the
        # summary router) — the app-level NarrareError handler answers.
        assert body["code"] == "NOT_FOUND"
        assert "detail" in body
        assert "text/event-stream" not in response.headers.values()
