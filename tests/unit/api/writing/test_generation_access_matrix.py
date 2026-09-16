"""RT-S6 — IDOR regression tests: chapter-access gate on writing generation.

Before the S6 fix, the six writing generation surfaces checked only chapter
EXISTENCE (``GenerationRepository.chapter_exists`` / a bare chapter load) —
any authenticated caller could start a generation against a FOREIGN chapter:
a ``generation_request`` row was created for the victim's chapter (request-row
pollution + owner-blocking via the unique active index) and the KB/series LLM
enrichment ran unscoped against the foreign novel.  Inline-suggest
additionally leaked foreign chapter metadata (title, POV) into the prompt.

The fix wires the S5 helper ``verify_chapter_access`` (chapter exists ∧
chapter∈novel ∧ novel∈caller → else indistinguishable ``NotFoundError``) into
every validate/start path, BEFORE any write, LLM enrichment, or request-row
creation.  Validation order per the plan: ownership → input → active-conflict.

Matrix, parametrized over generate / extend / rewrite / co-author /
style-variants / suggest:
1. owner → success unchanged (request row created / stream started),
2. foreign chapter (novel owned by another user) → 404 shape AND zero
   GenerationRequest rows AND the pipeline/registry never invoked,
3. unknown chapter → 404 identical in shape to the foreign case,
4. chapter∉novel → 404 (an owned novel must not unlock foreign chapters),
5. owner + active session → ConflictError (409 semantics preserved),
6. foreign + active session → 404 (ownership precedes the conflict check —
   a 409 would leak the chapter's existence).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.shared.errors import ConflictError, NotFoundError
from tests.factories import make_chapter, make_novel
from tests.unit.api.writing._matrix_requests import request_for_kind

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.repository import GenerationRepository
    from narrare_core.llm.result import StreamChunk

USER_A = uuid4()  # rightful owner of the novel + chapter
USER_B = uuid4()  # foreign caller

CONFIG = ResolvedModelConfig(
    provider_name="test",
    model_id="test-model",
    temperature=0.7,
    max_tokens=4000,
)

# The S6a slice wires generate/extend/rewrite; S6b adds co-author,
# style-variants and suggest.  The matrix is identical for all six.
KINDS = ["generate", "extend", "rewrite", "coauthor", "style_variant", "suggest"]


# ---------------------------------------------------------------------------
# Fakes (ADR-030 — real fakes for domain repos, guards for LLM boundaries)
# ---------------------------------------------------------------------------


class _FakeChapterRepo:
    """In-memory ``ChapterRepository`` stand-in."""

    def __init__(self, *chapters: Chapter) -> None:
        self._chapters: dict[UUID, Chapter] = {c.id: c for c in chapters}

    async def get(self, chapter_id: UUID) -> Chapter | None:
        return self._chapters.get(chapter_id)


class _FakeNovelRepo:
    """In-memory ``NovelRepository`` stand-in mapping novel → owner."""

    def __init__(self, ownership: dict[UUID, UUID]) -> None:
        self._ownership = ownership

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        if self._ownership.get(novel_id) != user_id:
            return None
        return make_novel(id=novel_id, user_id=user_id)


def _gen_repo(*, active: object = None) -> MagicMock:
    """``GenerationRepository`` mock recording every row-creating call."""
    repo = MagicMock(
        spec=[
            "create",
            "create_if_no_active",
            "get_active_for_chapter",
            "get_by_id",
            "update_status",
        ]
    )
    repo.create = AsyncMock(return_value=uuid4())
    repo.create_if_no_active = AsyncMock(return_value=uuid4())
    repo.get_active_for_chapter = AsyncMock(return_value=active)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update_status = AsyncMock()
    return repo


def _processor() -> MagicMock:
    proc = MagicMock(spec=["process"])
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return proc


def _pipeline(*, working: bool) -> MagicMock:
    """Pipeline mock: guard (fails on touch) or one-final-chunk stream."""
    pipeline = MagicMock(spec=["generate"])

    if working:

        async def _stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
            from narrare_core.llm.result import StreamChunk as Chunk
            from narrare_core.llm.result import TokenUsage

            yield Chunk(text="done", is_final=True, usage=TokenUsage(1, 1, 2))

        pipeline.generate = _stream
    else:

        def _must_not_stream(*args: object, **kwargs: object) -> Any:
            raise AssertionError("pipeline invoked — LLM enrichment despite the gate")

        pipeline.generate = _must_not_stream
    return pipeline


# Style-variant has a lazy-runtime branch in ``_make_service`` too
# (ADR-086 L35, pinned via ``_style_variant_factories``).


def _requests(kind: str) -> Any:
    """Valid request payload per endpoint kind (builder moved per RULE-04)."""
    return request_for_kind(kind)


def _make_service(
    kind: str,
    gen_repo: MagicMock,
    chapter_repo: _FakeChapterRepo,
    novel_repo: _FakeNovelRepo,
    *,
    working_llm: bool = False,
) -> Any:
    """Build the real service for ``kind`` over the given fakes/mocks.

    ``working_llm=False`` (default) arms guard fakes that fail the test the
    moment the LLM boundary is reached — correct for the failure matrix.
    ``working_llm=True`` streams one final chunk for the owner path.
    """
    cr = cast("ChapterRepository", chapter_repo)
    nr = cast("NovelRepository", novel_repo)

    if kind == "suggest":
        # Builder lives in _suggest_factories (RULE-04 split, L32 ratchet).
        from tests.unit.api.writing._suggest_factories import make_matrix_suggest_service

        return make_matrix_suggest_service(
            registry_guarded=not working_llm,
            chapter_repo=cr,
            novel_repo=nr,
            config=CONFIG,
        )

    if kind == "rewrite":
        from tests.unit.api.writing._rewrite_factories import make_matrix_rewrite_service

        return make_matrix_rewrite_service(
            repo=cast("GenerationRepository", gen_repo),
            pipeline=_pipeline(working=working_llm),
            chapter_repo=cr,
            novel_repo=nr,
            draft_processor=_processor(),
            config=CONFIG,
        )

    if kind == "extend":
        # ADR-086 L32: lazy-runtime ctor — pins the matrix pipeline verbatim,
        # so the guard/working-mock semantics are unchanged.
        from tests.unit.api.writing._extend_factories import make_matrix_extend_service

        return make_matrix_extend_service(
            repo=cast("GenerationRepository", gen_repo),
            pipeline=_pipeline(working=working_llm),
            chapter_repo=cr,
            novel_repo=nr,
            draft_processor=_processor(),
            config=CONFIG,
        )

    if kind == "coauthor":
        # ADR-086 L31: lazy-runtime ctor — pins the matrix pipeline
        # verbatim, so the guard/working-mock semantics are unchanged.
        from tests.unit.api.writing._coauthor_factories import make_matrix_coauthor_service

        return make_matrix_coauthor_service(
            repo=cast("GenerationRepository", gen_repo),
            pipeline=_pipeline(working=working_llm),
            chapter_repo=cr,
            novel_repo=nr,
            draft_processor=_processor(),
            config=CONFIG,
        )

    if kind == "style_variant":
        # ADR-086 L35: lazy-runtime ctor — pins the matrix pipeline
        # verbatim, so the guard/working-mock semantics are unchanged.
        from tests.unit.api.writing._style_variant_factories import (
            make_matrix_style_variant_service,
        )

        return make_matrix_style_variant_service(
            repo=cast("GenerationRepository", gen_repo),
            pipeline=_pipeline(working=working_llm),
            chapter_repo=cr,
            novel_repo=nr,
            draft_processor=_processor(),
            config=CONFIG,
        )

    from narrare.writing.service import WritingService

    services: dict[str, type[Any]] = {"generate": WritingService}
    return services[kind](
        repo=cast("GenerationRepository", gen_repo),
        pipeline=_pipeline(working=working_llm),
        draft_processor=_processor(),
        config=CONFIG,
        chapter_repo=cr,
        novel_repo=nr,
    )


async def _collect(stream: AsyncIterator[StreamChunk]) -> list[StreamChunk]:
    return [chunk async for chunk in stream]


async def _invoke(kind: str, service: Any, chapter_id: UUID, novel_id: UUID, user: UUID) -> Any:
    """Drive the gated entry point of ``kind`` for ``user``."""
    request = _requests(kind)
    if kind == "generate":
        return await service.start_generation(chapter_id, novel_id, str(user), request)
    if kind == "extend":
        return await service.start_extend(chapter_id, novel_id, str(user), request)
    if kind == "rewrite":
        return await service.start_rewrite(chapter_id, novel_id, str(user), request)
    if kind == "coauthor":
        return await _collect(service.stream_coauthor(chapter_id, novel_id, str(user), request))
    if kind == "style_variant":
        return await _collect(service.stream_variant(chapter_id, novel_id, str(user), request))
    return await _collect(service.suggest_inline(chapter_id, str(user), request))


def _row_creators(gen_repo: MagicMock) -> int:
    """Number of request-row-creating calls recorded by the gen repo."""
    return gen_repo.create.await_count + gen_repo.create_if_no_active.await_count


class TestGenerationAccessMatrix:
    """Foreign/unknown/owner matrix over the six writing generation surfaces."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", KINDS)
    async def test_owner_succeeds(self, kind: str) -> None:
        """Owner: chapter∈novel∈caller → request row created / stream runs."""
        novel_id = uuid4()
        chapter = make_chapter(novel_id=novel_id)
        gen_repo = _gen_repo()

        service = _make_service(
            kind,
            gen_repo,
            _FakeChapterRepo(chapter),
            _FakeNovelRepo({novel_id: USER_A}),
            working_llm=True,
        )
        result = await _invoke(kind, service, chapter.id, novel_id, USER_A)

        assert result is not None
        assert _row_creators(gen_repo) == (0 if kind == "suggest" else 1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", KINDS)
    async def test_foreign_novel_404_no_row_no_llm(self, kind: str) -> None:
        """USER_B calling with USER_A's chapter/novel → 404 BEFORE any write
        or LLM enrichment; zero GenerationRequest rows created."""
        novel_id = uuid4()
        chapter = make_chapter(novel_id=novel_id)
        gen_repo = _gen_repo()

        service = _make_service(
            kind, gen_repo, _FakeChapterRepo(chapter), _FakeNovelRepo({novel_id: USER_A})
        )
        with pytest.raises(NotFoundError, match="Chapter"):
            await _invoke(kind, service, chapter.id, novel_id, USER_B)

        assert _row_creators(gen_repo) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", KINDS)
    async def test_unknown_chapter_404_same_shape(self, kind: str) -> None:
        """Unknown chapter id → the identical NotFoundError the foreign case
        raises (anti-enumeration)."""
        novel_id = uuid4()
        foreign_chapter = make_chapter(novel_id=novel_id)
        unknown_chapter_id = uuid4()
        gen_repo = _gen_repo()

        service = _make_service(
            kind, gen_repo, _FakeChapterRepo(foreign_chapter), _FakeNovelRepo({novel_id: USER_A})
        )
        with pytest.raises(NotFoundError) as foreign_exc:
            await _invoke(kind, service, foreign_chapter.id, novel_id, USER_B)
        with pytest.raises(NotFoundError) as unknown_exc:
            await _invoke(kind, service, unknown_chapter_id, novel_id, USER_B)

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Chapter ({foreign_chapter.id}) not found"
        assert str(unknown_exc.value) == f"Chapter ({unknown_chapter_id}) not found"
        assert _row_creators(gen_repo) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", KINDS)
    async def test_chapter_not_in_addressed_novel_404(self, kind: str) -> None:
        """The caller OWNS the addressed novel but the chapter belongs to a
        different novel → 404."""
        novel_id = uuid4()
        chapter = make_chapter(novel_id=uuid4())  # some OTHER novel
        gen_repo = _gen_repo()

        service = _make_service(
            kind, gen_repo, _FakeChapterRepo(chapter), _FakeNovelRepo({novel_id: USER_A})
        )
        with pytest.raises(NotFoundError, match="Chapter"):
            await _invoke(kind, service, chapter.id, novel_id, USER_A)

        assert _row_creators(gen_repo) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", [k for k in KINDS if k != "suggest"])
    async def test_owner_active_session_still_conflicts(self, kind: str) -> None:
        """Owner with an active generation → ConflictError preserved (409
        semantics unchanged for the rightful owner)."""
        novel_id = uuid4()
        chapter = make_chapter(novel_id=novel_id)
        gen_repo = _gen_repo(active=MagicMock(spec=["status"]))
        if kind == "generate":
            # generate has no pre-check; the conflict fires inside
            # create_if_no_active (atomic guard).
            gen_repo.create_if_no_active = AsyncMock(side_effect=ConflictError("already active"))
            gen_repo.get_active_for_chapter = AsyncMock(return_value=None)

        service = _make_service(
            kind, gen_repo, _FakeChapterRepo(chapter), _FakeNovelRepo({novel_id: USER_A})
        )
        with pytest.raises(ConflictError):
            await _invoke(kind, service, chapter.id, novel_id, USER_A)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", [k for k in KINDS if k != "suggest"])
    async def test_foreign_with_active_session_404_not_409(self, kind: str) -> None:
        """Foreign caller while a generation is active on the chapter → 404,
        NOT 409: ownership runs before the conflict check, so the active row
        never confirms the chapter's existence to a foreign caller."""
        novel_id = uuid4()
        chapter = make_chapter(novel_id=novel_id)
        gen_repo = _gen_repo(active=MagicMock(spec=["status"]))

        service = _make_service(
            kind, gen_repo, _FakeChapterRepo(chapter), _FakeNovelRepo({novel_id: USER_A})
        )
        with pytest.raises(NotFoundError, match="Chapter"):
            await _invoke(kind, service, chapter.id, novel_id, USER_B)

        assert _row_creators(gen_repo) == 0
