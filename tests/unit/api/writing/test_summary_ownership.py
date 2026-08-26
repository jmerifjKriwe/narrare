"""S4 — IDOR regression tests: ownership gate on chapter summarization.

Before the S4 fix, ``POST /summary/chapters/{chapter_id}`` had no
``user_id`` at all: ``ChapterSummaryService.summarize`` loaded ANY
chapter by bare id, fed its content to the LLM, and wrote the resulting
summary onto the foreign chapter via ``update_summary`` — a cross-tenant
READ (chapter content → LLM) plus WRITE (victim's chapter row mutated).

The fix is Pattern B (plan S4): the router threads ``CurrentUserIdDep``
into ``summarize``; directly after the chapter None-check — BEFORE the
content load, the LLM call, and the ``update_summary`` write — the
service gates ``novel_repo.get_by_id(chapter.novel_id, UUID(user_id))``
and raises ``NotFoundError("Chapter", chapter_id)`` on ``None``, so
foreign and unknown chapters are indistinguishable (anti-enumeration).

Matrix (plan S4): (1) owner → 200 flow unchanged (summary generated and
persisted), (2) foreign chapter → 404-shape ``NotFoundError`` AND no
side effect on the victim's chapter (``update_summary`` never called,
zero LLM calls), (3) unknown chapter → identical 404, (4) the gate
precedes even the empty-content early return.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.writing.summary_deps import get_summary_service
from narrare.writing.summary_service import ChapterSummaryService
from narrare_core.agents.summary_types import SummaryOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter

if TYPE_CHECKING:
    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"

USER_A = uuid4()  # rightful owner of the novel + chapter
USER_B = uuid4()  # foreign caller


# ---------------------------------------------------------------------------
# Fakes (ADR-030 — fake-based, not MagicMock)
# ---------------------------------------------------------------------------


class _FakeChapterRepo:
    """In-memory ``ChapterRepository`` stand-in (``get``/``update_summary``)."""

    def __init__(self, *chapters: Chapter) -> None:
        self._chapters: dict[UUID, Chapter] = {c.id: c for c in chapters}
        self.update_summary_calls: list[tuple[UUID, str]] = []

    async def get(self, chapter_id: UUID) -> Chapter | None:
        return self._chapters.get(chapter_id)

    async def update_summary(self, chapter: Chapter, summary: str) -> Chapter:
        self.update_summary_calls.append((chapter.id, summary))
        chapter.summary = summary
        return chapter


class _FakeNovelRepo:
    """In-memory ``NovelRepository`` stand-in mapping novel → owner."""

    def __init__(self, ownership: dict[UUID, UUID]) -> None:
        self._ownership = ownership
        self.get_by_id_calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        self.get_by_id_calls.append((novel_id, user_id))
        if self._ownership.get(novel_id) != user_id:
            return None
        return object()  # service only checks existence


class _FakeSummaryAgent:
    """``ChapterSummaryAgent`` stand-in returning a canned SummaryOutput.

    Counts ``run`` invocations so tests can prove the LLM was never
    called for a foreign chapter (ADR-030 fake, not MagicMock).
    """

    def __init__(self, output: SummaryOutput | None = None) -> None:
        self._output = output
        self.run_calls: int = 0

    async def run(self, *, prompt: str, deps: object) -> SummaryOutput:
        self.run_calls += 1
        if self._output is None:
            raise AssertionError("LLM agent.run must not be called for foreign chapters")
        return self._output


def _make_service(
    chapter_repo: _FakeChapterRepo,
    novel_repo: _FakeNovelRepo,
    *,
    registry: AsyncMock | None = None,
) -> ChapterSummaryService:
    """Build a real ChapterSummaryService over the fake repositories."""
    if registry is None:
        from pydantic_ai.models import Model

        registry = AsyncMock()
        registry.get_model = AsyncMock(return_value=MagicMock(spec=Model))
    composer = AsyncMock()
    composer.build = AsyncMock(
        return_value=ComposedPrompt(system="You are a summarizer.", user="Summarize.")
    )
    return ChapterSummaryService(
        registry=registry,
        config=ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            temperature=0.3,
            max_tokens=1000,
        ),
        chapter_repo=cast("ChapterRepository", chapter_repo),
        novel_repo=cast("NovelRepository", novel_repo),
        composer=composer,
    )


# ---------------------------------------------------------------------------
# Service level — ownership matrix
# ---------------------------------------------------------------------------


class TestSummarizeOwnership:
    """``summarize`` gates chapter→novel ownership before any effect."""

    @pytest.mark.asyncio
    async def test_owner_summarizes_and_persists(self) -> None:
        """Owner flow unchanged: LLM runs, summary written to the chapter."""
        chapter = make_chapter(content="The harbour lights flickered...", title="Ch 1")
        chapter_repo = _FakeChapterRepo(chapter)
        novel_repo = _FakeNovelRepo({chapter.novel_id: USER_A})
        service = _make_service(chapter_repo, novel_repo)
        fake_agent = _FakeSummaryAgent(
            output=SummaryOutput(summary="A storm approaches.", word_count=3)
        )

        with patch(
            "narrare.writing.summary_service.ChapterSummaryAgent",
            return_value=fake_agent,
        ):
            result = await service.summarize(chapter.id, user_id=str(USER_A))

        assert result.summary == "A storm approaches."
        assert fake_agent.run_calls == 1
        assert chapter_repo.update_summary_calls == [(chapter.id, "A storm approaches.")]

    @pytest.mark.asyncio
    async def test_foreign_chapter_raises_not_found_with_no_llm_call_or_write(self) -> None:
        """USER_B summarizing USER_A's chapter → NotFoundError BEFORE the
        content load: zero LLM calls, victim chapter never written."""
        chapter = make_chapter(content="Private content of USER_A...", title="Ch 1")
        chapter_repo = _FakeChapterRepo(chapter)
        novel_repo = _FakeNovelRepo({chapter.novel_id: USER_A})
        registry = AsyncMock()
        service = _make_service(chapter_repo, novel_repo, registry=registry)
        fake_agent = _FakeSummaryAgent()  # raises if the LLM is ever invoked

        with (
            patch(
                "narrare.writing.summary_service.ChapterSummaryAgent",
                return_value=fake_agent,
            ),
            pytest.raises(NotFoundError, match="Chapter"),
        ):
            await service.summarize(chapter.id, user_id=str(USER_B))

        # No LLM involvement at all — not even model resolution.
        assert fake_agent.run_calls == 0
        registry.get_model.assert_not_awaited()
        # No side effect on the victim's chapter.
        assert chapter_repo.update_summary_calls == []
        assert chapter.summary is None
        # The ownership lookup ran with the CALLER's id.
        assert novel_repo.get_by_id_calls == [(chapter.novel_id, USER_B)]

    @pytest.mark.asyncio
    async def test_unknown_chapter_raises_not_found_before_novel_lookup(self) -> None:
        chapter_repo = _FakeChapterRepo()
        novel_repo = _FakeNovelRepo({})
        service = _make_service(chapter_repo, novel_repo)

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.summarize(uuid4(), user_id=str(USER_B))

        assert novel_repo.get_by_id_calls == []
        assert chapter_repo.update_summary_calls == []

    @pytest.mark.asyncio
    async def test_foreign_and_unknown_chapter_are_indistinguishable(self) -> None:
        """Anti-enumeration: foreign vs unknown chapter → identical error
        type and message shape (404 body indistinguishable)."""
        foreign_chapter = make_chapter(content="USER_A's content", title="Ch 1")
        foreign_repo = _FakeChapterRepo(foreign_chapter)
        foreign_service = _make_service(
            foreign_repo, _FakeNovelRepo({foreign_chapter.novel_id: USER_A})
        )
        unknown_chapter_id = uuid4()
        unknown_service = _make_service(_FakeChapterRepo(), _FakeNovelRepo({}))

        with pytest.raises(NotFoundError) as foreign_exc:
            await foreign_service.summarize(foreign_chapter.id, user_id=str(USER_B))
        with pytest.raises(NotFoundError) as unknown_exc:
            await unknown_service.summarize(unknown_chapter_id, user_id=str(USER_B))

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Chapter ({foreign_chapter.id}) not found"
        assert str(unknown_exc.value) == f"Chapter ({unknown_chapter_id}) not found"

    @pytest.mark.asyncio
    async def test_gate_precedes_empty_content_early_return(self) -> None:
        """Gate ordering: even a FOREIGN chapter with EMPTY content is
        rejected — the ownership check runs before the content load and
        its empty-chapter early return."""
        chapter = make_chapter(content="", title="Empty")
        chapter_repo = _FakeChapterRepo(chapter)
        novel_repo = _FakeNovelRepo({chapter.novel_id: USER_A})
        service = _make_service(chapter_repo, novel_repo)

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.summarize(chapter.id, user_id=str(USER_B))

        assert chapter_repo.update_summary_calls == []


# ---------------------------------------------------------------------------
# Router level — identity threading
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Test app with overridden DB/auth dependencies (no real I/O)."""
    application = create_app()

    async def _mock_session() -> AsyncMock:
        mock = AsyncMock()
        mock.execute = AsyncMock()
        return mock

    async def _mock_auth() -> str:
        return TEST_USER_ID

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class TestSummarizeRouterThreading:
    """The router threads ``CurrentUserIdDep`` into the service call."""

    @pytest.mark.asyncio
    async def test_router_passes_authenticated_user_id_to_service(self, app, client) -> None:
        """POST /summary/chapters/{id} must hand the authenticated user id
        to ``summarize`` — without it the service gate has no identity."""
        from narrare.writing.summary_contracts import SummaryResult

        mock_service = AsyncMock()
        mock_service.summarize = AsyncMock(return_value=SummaryResult(summary="s", word_count=1))
        app.dependency_overrides[get_summary_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/summary/chapters/{uuid4()}",
            json={"max_sentences": 3, "language": "en"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_service.summarize.assert_awaited_once()
        assert mock_service.summarize.await_args.kwargs["user_id"] == TEST_USER_ID
