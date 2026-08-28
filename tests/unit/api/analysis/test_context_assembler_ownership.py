"""S12a — IDOR regression tests: ownership gate on beta-reader context assembly.

Before the S12a fix, ``ContextAssembler.build_context`` resolved access by bare
``novel_id``: a foreign caller's beta-reader request loaded the victim's
chapters and KB entities into the LLM context, and the novel-metadata lookup
DEGRADED to defaults on lookup failure (RULE-11 anti-pattern) — silently
masking foreign access (genre="", language="en", analysis still ran).

The fix (plan S12a, Pattern B) makes ``user_id`` REQUIRED and moves the
ownership gate to Step 0: a single user-scoped ``novel_repo.get_by_id`` lookup
gates AND supplies the genre/language metadata — BEFORE any chapter load
(``list_by_novel``), KB fetch (``fetch_context``), or LLM call. Lookup
``None`` → ``NotFoundError`` (foreign ≡ unknown → 404 via the global
handler); lookup failure propagates (no degrade). ``BetaReaderService``
passes the gate error through unwrapped (never ``AnalysisError``/500).

HTTP-level mapping is covered by the global ``NarrareError`` handler
(``_app/main.py``); this file proves the service-boundary contract.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from narrare.analysis.beta_reader_service import BetaReaderService
from narrare.analysis.context_assembler import ContextAssembler
from narrare.analysis.contracts import FeedbackCategory
from narrare.analysis.schemas import (
    BetaReaderDeepDiveRequest,
    BetaReaderOverallAssessment,
    BetaReaderRequest,
    BetaReaderResponse,
)
from narrare_core.llm import ResolvedModelConfig
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.context_contracts import KBContextBundle, KBContextProviderProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.context._render_options import RenderOptions

USER_A = uuid4()  # rightful owner of NOVEL_ID (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A
FOREIGN_NOVEL_ID = uuid4()  # owned by USER_B (a real novel — just not the caller's)

GENRE = "Fantasy"
LANGUAGE = "de"

CHAPTER_IDS = [uuid4(), uuid4()]

_OWNERSHIP = {NOVEL_ID: USER_A, FOREIGN_NOVEL_ID: USER_B}


# ---------------------------------------------------------------------------
# Fakes (ADR-030 fake-first — recording, ownership-aware)
# ---------------------------------------------------------------------------


def _make_novel(novel_id: UUID, owner: UUID) -> SimpleNamespace:
    """Novel-like object carrying the metadata the assembler extracts."""
    return SimpleNamespace(id=novel_id, user_id=owner, genre=GENRE, writing_language=LANGUAGE)


class RecordingNovelRepo:
    """Fake NovelRepositoryProtocol with a real ownership map.

    Records ``get_by_id`` (user-scoped) AND ``get`` (system-level) calls so
    tests can assert the old unscoped fallback path is gone.
    """

    def __init__(self, ownership: dict[UUID, UUID]) -> None:
        self._ownership = ownership
        self.get_by_id_calls: list[tuple[UUID, UUID]] = []
        self.get_calls: list[UUID] = []
        self.error: Exception | None = None

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> SimpleNamespace | None:
        self.get_by_id_calls.append((novel_id, user_id))
        if self.error is not None:
            raise self.error
        if self._ownership.get(novel_id) == user_id:
            return _make_novel(novel_id, user_id)
        return None

    async def get(self, novel_id: UUID) -> SimpleNamespace | None:
        self.get_calls.append(novel_id)
        return _make_novel(novel_id, self._ownership.get(novel_id, USER_A))


class RecordingChapterRepo:
    """Fake ChapterRepositoryProtocol — records chapter loads."""

    def __init__(self) -> None:
        self.list_by_novel_calls: list[UUID] = []

    async def list_by_novel(self, novel_id: UUID) -> list[SimpleNamespace]:
        self.list_by_novel_calls.append(novel_id)
        return [
            SimpleNamespace(
                id=chapter_id,
                novel_id=novel_id,
                title=f"Chapter {i}",
                content="Content " * 200,
                summary="",
                position=i,
                word_count=2000,
            )
            for i, chapter_id in enumerate(CHAPTER_IDS)
        ]


class RecordingKBProvider:
    """Fake KBContextProviderProtocol — records fetches, renders empty."""

    def __init__(self) -> None:
        self.fetch_context_calls: list[UUID] = []

    async def fetch_context(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle:
        from narrare.kb.context_contracts import KBContextBundle

        self.fetch_context_calls.append(novel_id)
        return KBContextBundle.empty(options)


def _make_assembler(
    novel_repo: RecordingNovelRepo | None = None,
) -> tuple[ContextAssembler, RecordingChapterRepo, RecordingKBProvider, RecordingNovelRepo]:
    """Assembler over recording fakes with the real ownership map."""
    novel_repo = novel_repo or RecordingNovelRepo(_OWNERSHIP)
    chapter_repo = RecordingChapterRepo()
    kb_provider = RecordingKBProvider()
    assembler = ContextAssembler(
        chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
        kb_context_provider=cast("KBContextProviderProtocol", kb_provider),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
    )
    return assembler, chapter_repo, kb_provider, novel_repo


def _cached_response() -> BetaReaderResponse:
    """Minimal valid Phase 1 response for the cache-hit owner path."""
    return BetaReaderResponse(
        novel_id=str(NOVEL_ID),
        chapter_ids=[str(CHAPTER_IDS[0])],
        total_word_count=4000,
        strengths=[],
        feedback=[],
        questions=[],
        overall=BetaReaderOverallAssessment(
            summary="Solid",
            reader_engagement=7,
            emotional_impact=6,
            pacing_score=5,
            prose_quality=7,
            plot_progression=6,
            character_development=5,
        ),
        analyzed_at="2026-08-28T00:00:00+00:00",
        cache_key="abc123",
    )


def _make_service(
    assembler: ContextAssembler, cache_hit: BetaReaderResponse | None = None
) -> tuple[BetaReaderService, AsyncMock, AsyncMock]:
    """BetaReaderService over a REAL assembler + spec'd cache/registry mocks."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=cache_hit.model_dump_json() if cache_hit else None)
    cache.set = AsyncMock()
    registry = AsyncMock()
    composer = AsyncMock()
    service = BetaReaderService(
        context_assembler=assembler,
        cache=cache,
        registry=registry,
        config=ResolvedModelConfig(
            provider_name="test", model_id="test", temperature=0.7, max_tokens=4096
        ),
        composer=composer,
    )
    return service, registry, cache


# ---------------------------------------------------------------------------
# ContextAssembler — Step 0 ownership gate
# ---------------------------------------------------------------------------


class TestBuildContextOwnership:
    """``build_context`` gates ownership BEFORE any chapter/KB load."""

    async def test_owner_context_assembled_unchanged(self) -> None:
        """Matrix case (1): the rightful owner's flow is unchanged — genre and
        language flow from the user-scoped novel lookup."""
        assembler, chapter_repo, kb_provider, novel_repo = _make_assembler()

        deps = await assembler.build_context(NOVEL_ID, CHAPTER_IDS, user_id=USER_A)

        assert deps.genre == GENRE
        assert deps.language == LANGUAGE
        assert deps.word_count == 4000
        # The gate ran with the CALLER's id — and only the user-scoped lookup.
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert novel_repo.get_calls == []
        assert chapter_repo.list_by_novel_calls == [NOVEL_ID]
        assert kb_provider.fetch_context_calls == [NOVEL_ID]

    async def test_foreign_novel_denied_before_any_chapter_or_kb_load(self) -> None:
        """Matrix case (2)+(4): foreign novel → NotFoundError BEFORE the
        victim's chapters or KB entities are loaded (zero exfiltration)."""
        assembler, chapter_repo, kb_provider, novel_repo = _make_assembler()

        with pytest.raises(NotFoundError, match="Novel"):
            await assembler.build_context(NOVEL_ID, CHAPTER_IDS, user_id=USER_B)

        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_B)]
        assert chapter_repo.list_by_novel_calls == []
        assert kb_provider.fetch_context_calls == []

    async def test_unknown_novel_indistinguishable_from_foreign(self) -> None:
        """Matrix case (3): unknown novel ≡ foreign novel (anti-enumeration)."""
        assembler, _, _, _ = _make_assembler()
        unknown_novel_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await assembler.build_context(NOVEL_ID, CHAPTER_IDS, user_id=USER_B)
        with pytest.raises(NotFoundError) as unknown_exc:
            await assembler.build_context(unknown_novel_id, CHAPTER_IDS, user_id=USER_B)

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"

    async def test_lookup_failure_propagates_no_degrade_to_defaults(self) -> None:
        """RULE-11 regression: the old ``_fetch_novel_metadata`` swallowed ANY
        exception and degraded to ``("", "en")`` — masking foreign access. A
        failing lookup must now propagate, never silently run the analysis."""
        novel_repo = RecordingNovelRepo(_OWNERSHIP)
        novel_repo.error = RuntimeError("db down")
        assembler, chapter_repo, _, _ = _make_assembler(novel_repo)

        with pytest.raises(RuntimeError, match="db down"):
            await assembler.build_context(NOVEL_ID, CHAPTER_IDS, user_id=USER_A)

        assert chapter_repo.list_by_novel_calls == []


# ---------------------------------------------------------------------------
# BetaReaderService — gate error passes through unwrapped (analyze + deep-dive)
# ---------------------------------------------------------------------------


class TestBetaReaderServiceOwnership:
    """Both analysis phases surface the gate as 404 — never wrapped in 500."""

    async def test_analyze_foreign_novel_404_no_llm_no_cache(self) -> None:
        """Foreign novel on analyze → NotFoundError (not AnalysisError), no
        model resolution, no cache write."""
        assembler, _, _, _ = _make_assembler()
        service, registry, cache = _make_service(assembler)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.analyze(
                novel_id=NOVEL_ID,
                user_id=USER_B,
                request=BetaReaderRequest(chapter_ids=[str(CHAPTER_IDS[0])]),
            )

        registry.get_model.assert_not_awaited()
        cache.set.assert_not_awaited()

    async def test_deep_dive_foreign_novel_404_shares_the_gate(self) -> None:
        """Deep-dive (Phase 2) shares the assembly path → same gate, 404
        before the Phase 1 cache is even probed."""
        assembler, _, _, _ = _make_assembler()
        service, _, cache = _make_service(assembler)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.deep_dive(
                novel_id=NOVEL_ID,
                user_id=USER_B,
                request=BetaReaderDeepDiveRequest(
                    chapter_ids=[str(CHAPTER_IDS[0])],
                    category=FeedbackCategory.PLOT,
                    cache_key="abc123",
                ),
            )

        cache.get.assert_not_awaited()

    async def test_analyze_owner_cache_hit_flow_unchanged(self) -> None:
        """Matrix case (1): the owner still passes the gate and gets the
        cached Phase 1 result — no model resolution needed on a cache hit."""
        assembler, _, _, novel_repo = _make_assembler()
        service, registry, _ = _make_service(assembler, cache_hit=_cached_response())

        result = await service.analyze(
            novel_id=NOVEL_ID,
            user_id=USER_A,
            request=BetaReaderRequest(chapter_ids=[str(CHAPTER_IDS[0])]),
        )

        assert result.novel_id == str(NOVEL_ID)
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        registry.get_model.assert_not_awaited()
