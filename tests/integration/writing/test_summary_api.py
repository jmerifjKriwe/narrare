"""Integration suite for the chapter SUMMARY endpoint (ADR-086 L38 gap).

Covers the REST summarize endpoint end-to-end on the REAL
``get_summary_service`` factory. Unlike its extend/rewrite/suggest/style
siblings, the writing integration conftest does NOT patch the summary
factory — the production wiring (lazy ``LazyModelResolution`` +
token-limits composition, ADR-086 L38) runs on every node here, so no
re-patching is needed:

- happy path — seeded provider (routing cascade resolves) + seeded
  novel/chapter content → 200, summary persisted to the chapter row;
  the LLM boundary is faked at its two seams: the registry via the
  canonical ``FakeModelRegistry`` at the factory-import site
  (``narrare.writing.summary_deps.get_model_registry`` — the real
  registry would reject the seeded synthetic provider name) and the
  agent via ``narrare.writing._summary_invocation.ChapterSummaryAgent``
  (the unit-suite convention — ADR-030 fake at the domain boundary, no
  real LLM call);
- 401 unauthenticated;
- ownership 404 — foreign chapter (owner is a second user) → 404 even
  though the caller has NO provider configuration: the service's
  ownership gate fires BEFORE the first-use resolution
  (gate-before-resolution, foreign ≡ unknown — anti-enumeration);
- 422 invalid body — ``max_sentences`` outside [1, 20] → 422 wins over
  any 400: the lazy factory performs no cascade work at construction,
  so body validation is never preempted (the deferral contract);
- loud 400 — owned chapter + unconfigured provider → the first-use
  composition raises ``ConfigurationError`` (``NO_AI_PROVIDER``) and
  surfaces as a plain JSON 400 (REST, no SSE media type).

Mirrors ``tests/integration/writing/test_extend_lazy_resolution.py``
(ADR-086 L32 convention).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

_SUMMARY_URL = "/api/v1/summary/chapters"

_CONTENT = (
    "The old lighthouse keeper climbed the spiral stairs every evening "
    "to light the lamp before the fishing boats returned home."
)


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


async def _create_novel_with_content(
    client: AsyncClient,
    auth_headers: dict[str, str],
    *,
    title: str,
) -> tuple[str, str]:
    """Create a novel plus a content-bearing chapter via the API."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": title, "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": f"{title} — Chapter 1", "position": 1, "content": _CONTENT},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    return novel_id, chapter_resp.json()["id"]


class TestSummaryApiIntegration:
    """Real-factory contract of POST /api/v1/summary/chapters/{id}."""

    async def test_summarize_with_seeded_provider_returns_and_persists_summary(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        """Happy path: seeded cascade → 200 + summary persisted to the row.

        The REAL factory resolves both cascades (routing + token limits),
        the ownership gate passes, the KB bundle degrades to empty (RULE-11,
        no KB rows), the faked agent returns controlled output, and the real
        ``ChapterRepository.update_summary`` persists it.
        """
        from uuid import UUID

        from sqlalchemy import select

        from narrare.chapters.models import Chapter
        from narrare_core.agents.summary_types import SummaryOutput
        from narrare_core.llm import LLMIntent
        from tests.fakes.fake_llm_gateway import FakeModelRegistry

        user_id = await _current_user_id(auth_headers)
        await _seed_default_provider(db_session, user_id)
        novel_id, chapter_id = await _create_novel_with_content(
            client, auth_headers, title="Summary Happy Path Novel"
        )

        agent = AsyncMock()
        agent.run = AsyncMock(
            return_value=SummaryOutput(
                summary="A keeper lights the lamp each evening.",
                word_count=7,
                key_points=["The keeper lights the lamp"],
            )
        )
        registry = FakeModelRegistry()

        # Optional-body contract: no JSON body → defaults (max_sentences=4).
        with (
            patch(
                "narrare.writing._summary_invocation.ChapterSummaryAgent",
                return_value=agent,
            ),
            patch(
                "narrare.writing.summary_deps.get_model_registry",
                return_value=registry,
            ),
        ):
            response = await client.post(
                f"{_SUMMARY_URL}/{chapter_id}",
                params={"novel_id": novel_id},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["summary"] == "A keeper lights the lamp each evening."
        assert body["word_count"] == 7
        assert body["key_points"] == ["The keeper lights the lamp"]

        # Wiring evidence: the frozen first-use runtime reached the
        # registry's prepare() assembly point — seeded provider/model ids,
        # the factory's sampling overlay (temperature 0.3), the SUMMARIZE
        # intent, and the token-limits cascade's output cap.
        assert len(registry.prepare_calls) == 1
        prepare = registry.prepare_calls[0]
        assert prepare["intent"] == LLMIntent.SUMMARIZE
        config = prepare["config"]
        assert config is not None
        assert config.provider_name == "test"
        assert config.model_id == "test-model"
        assert config.temperature == 0.3
        assert prepare["usage_limits"] is not None

        chapter = await db_session.scalar(select(Chapter).where(Chapter.id == UUID(chapter_id)))
        assert chapter is not None
        assert chapter.summary == "A keeper lights the lamp each evening."

    async def test_summarize_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """No Authorization header → 401 before any service work."""
        response = await client.post(f"{_SUMMARY_URL}/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 401

    async def test_summarize_foreign_chapter_returns_404_before_resolution(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        """Foreign chapter → 404 even with the caller's provider unseeded.

        The ownership gate precedes the first-use resolution: a 400
        (NO_AI_PROVIDER) here would mean the gate fired after the
        cascade — the 404 proves gate-before-resolution (foreign ≡
        unknown, anti-enumeration). The ROUTER converts the service's
        ``NotFoundError`` into a bare ``HTTPException(404)`` (summary_router
        try/except), so the body carries ``detail`` only — the ``code``
        field exists solely on errors that reach the app-level
        ``NarrareError`` handler (e.g. the loud-400 node below).
        """
        import uuid
        from datetime import UTC, datetime

        from narrare._app.config import get_settings
        from narrare.auth.models import User
        from narrare.auth.security import create_access_token

        now = datetime.now(UTC)
        owner = User(
            id=uuid.uuid4(),
            email=f"summary-owner-{uuid.uuid4().hex[:12]}@example.com",
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
        _novel_id, chapter_id = await _create_novel_with_content(
            client, owner_headers, title="Summary Foreign Novel"
        )

        response = await client.post(
            f"{_SUMMARY_URL}/{chapter_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_summarize_with_invalid_body_returns_422_with_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """``max_sentences=99`` (le=20) → 422, not preempted by a 400.

        The REAL lazy factory does no routing/token-limit work at
        construction, so body validation completes before any cascade
        could raise NO_AI_PROVIDER (the caller here is unconfigured).
        """
        response = await client.post(
            f"{_SUMMARY_URL}/00000000-0000-0000-0000-000000000000",
            json={"max_sentences": 99},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_summarize_with_unconfigured_provider_returns_loud_400(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Owned chapter + no provider → 400 NO_AI_PROVIDER, plain JSON.

        Real chain, provider NOT seeded: the first-use composition raises
        ``ConfigurationError`` after the ownership gate; the handler maps
        it to a 400 REST response — no SSE media type (RULE-11, loud).
        """
        novel_id, chapter_id = await _create_novel_with_content(
            client, auth_headers, title="Summary Unconfigured Novel"
        )

        response = await client.post(
            f"{_SUMMARY_URL}/{chapter_id}",
            params={"novel_id": novel_id},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["code"] == "NO_AI_PROVIDER"
        assert "text/event-stream" not in response.headers.get("content-type", "")
