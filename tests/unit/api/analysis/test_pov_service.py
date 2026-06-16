"""Unit tests for POVService — access control, language, agent orchestration.

Uses Fake classes for all dependencies (no MagicMock).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from narrare.analysis.services.pov_service import POVService
from narrare_core.agents.pov_types import POVDetectionOutput
from narrare_core.analysis.types import POVResult
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import NotFoundError
from tests.fakes import FakeChapterRepository, FakeModelRegistry, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos
from tests.unit.api.analysis._fakes import FakePOVAgent, SeededKBRepository, SpyInvocationPipeline

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIG = ResolvedModelConfig(provider_name="anthropic", model_id="test-model")


def _pov_output(**overrides: Any) -> POVDetectionOutput:
    data: dict[str, Any] = {
        "scenes": [{"scene_index": 0, "pov_character": "Alice", "confidence": 0.9}],
        "issues": [],
        "pov_distribution": {"Alice": 1.0},
        "switch_count": 0,
        "analysis_type": "third_limited",
    }
    data.update(overrides)
    return POVDetectionOutput(**data)


def _make_service(
    content: str = "Alice saw the light.",
    kb_names: list[str] | None = None,
    writing_language: str = "en",
    invocation_pipeline: InvocationPipeline | None = None,
) -> tuple[Any, Any, POVService]:
    novel = make_novel(writing_language=writing_language)
    ch = make_chapter(novel_id=novel.id, content=content)
    nr, cr = FakeNovelRepository(), FakeChapterRepository()
    kb = SeededKBRepository(kb_names or [])
    seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
    svc = POVService(
        chapter_repo=cr,
        novel_repo=nr,
        kb_repo=kb,
        model_registry=FakeModelRegistry(),
        model_config=_CONFIG,
        invocation_pipeline=invocation_pipeline,
    )
    return novel, ch, svc


def _inject(svc: POVService, agent: FakePOVAgent) -> None:
    svc._get_agent = lambda: agent  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# A. analyze — happy path
# ---------------------------------------------------------------------------


class TestPOVAnalyzeHappyPath:
    @pytest.mark.asyncio
    async def test_returns_pov_result(self) -> None:
        novel, ch, svc = _make_service()
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        result = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert isinstance(result, POVResult)
        assert result.analysis_type == "third_limited"
        assert fake.run_called

    @pytest.mark.asyncio
    async def test_resolves_language_auto_from_novel(self) -> None:
        novel, ch, svc = _make_service(writing_language="de")
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, language="auto"
        )
        assert fake.last_deps.language == "de"

    @pytest.mark.asyncio
    async def test_language_override_not_auto(self) -> None:
        novel, ch, svc = _make_service(writing_language="de")
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, language="fr"
        )
        assert fake.last_deps.language == "fr"

    @pytest.mark.asyncio
    async def test_passes_known_characters_from_kb(self) -> None:
        novel, ch, svc = _make_service(kb_names=["Alice", "Bob"])
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert "Alice" in fake.last_deps.known_characters

    @pytest.mark.asyncio
    async def test_pov_type_hint_passed_to_deps(self) -> None:
        novel, ch, svc = _make_service()
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, pov_type="first_person"
        )
        assert fake.last_deps.pov_type_hint == "first_person"


# ---------------------------------------------------------------------------
# B. analyze — error cases
# ---------------------------------------------------------------------------


class TestPOVAnalyzeErrors:
    @pytest.mark.asyncio
    async def test_novel_not_found_raises(self) -> None:
        novel, ch, svc = _make_service()
        with pytest.raises(NotFoundError, match="Novel"):
            await svc.analyze(novel_id=uuid4(), chapter_ids=[ch.id], user_id=novel.user_id)

    @pytest.mark.asyncio
    async def test_chapter_not_found_raises(self) -> None:
        novel, _, svc = _make_service()
        with pytest.raises(NotFoundError, match="Chapter"):
            await svc.analyze(novel_id=novel.id, chapter_ids=[uuid4()], user_id=novel.user_id)

    @pytest.mark.asyncio
    async def test_agent_error_propagates(self) -> None:
        novel, ch, svc = _make_service()
        fake = FakePOVAgent(error=RuntimeError("LLM down"))
        _inject(svc, fake)
        with pytest.raises(RuntimeError, match="LLM down"):
            await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)


# ---------------------------------------------------------------------------
# C. analyze — empty text edge case
# ---------------------------------------------------------------------------


class TestPOVAnalyzeEmptyText:
    @pytest.mark.asyncio
    async def test_empty_chapter_returns_empty_result(self) -> None:
        novel, ch, svc = _make_service(content="")
        fake = FakePOVAgent()
        _inject(svc, fake)
        result = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert isinstance(result, POVResult)
        assert result.scenes == []
        assert not fake.run_called

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_empty_result(self) -> None:
        novel, ch, svc = _make_service(content="   \n\t  ")
        fake = FakePOVAgent()
        _inject(svc, fake)
        result = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert result.scenes == []
        assert not fake.run_called


# ---------------------------------------------------------------------------
# D. _resolve_characters + multiple chapters
# ---------------------------------------------------------------------------


class TestResolveCharacters:
    @pytest.mark.asyncio
    async def test_returns_character_names_from_kb(self) -> None:
        novel, _, svc = _make_service(kb_names=["Alice", "Bob"])
        names = await svc._resolve_characters(novel.id)
        assert "Alice" in names
        assert "Bob" in names

    @pytest.mark.asyncio
    async def test_empty_kb_returns_empty_list(self) -> None:
        novel, _, svc = _make_service(kb_names=[])
        names = await svc._resolve_characters(novel.id)
        assert names == []


class TestMultipleChapters:
    @pytest.mark.asyncio
    async def test_chapters_concatenated(self) -> None:
        novel = make_novel()
        ch1 = make_chapter(novel_id=novel.id, content="First scene.")
        ch2 = make_chapter(novel_id=novel.id, content="Second scene.")
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch1, ch2, novel_repo=nr, chapter_repo=cr)
        svc = POVService(
            chapter_repo=cr,
            novel_repo=nr,
            kb_repo=SeededKBRepository([]),
            model_registry=FakeModelRegistry(),
            model_config=_CONFIG,
        )
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch1.id, ch2.id], user_id=novel.user_id)
        assert "First scene." in fake.last_deps.text
        assert "Second scene." in fake.last_deps.text


# ---------------------------------------------------------------------------
# E. Invocation composition — verifies compose_invocation (ADR-048 Mode 2)
# ---------------------------------------------------------------------------


class TestInvocationComposition:
    """Verify the service routes through compose_invocation, not safe_record_evidence."""

    @pytest.mark.asyncio
    async def test_compose_invocation_called_with_pov_feature_id(self) -> None:
        """The pipeline prepare/finalize are invoked with feature_id analysis_pov."""
        spy = SpyInvocationPipeline()
        novel, ch, svc = _make_service(invocation_pipeline=spy)
        _inject(svc, FakePOVAgent(output=_pov_output()))
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)

        assert len(spy.prepare_calls) == 1
        assert spy.prepare_calls[0].feature_id == "analysis_pov"
        assert len(spy.finalize_calls) == 1
        assert spy.finalize_calls[0].feature_id == "analysis_pov"
