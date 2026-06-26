"""Unit tests for ReadabilityService — agent orchestration and merge logic.

Uses Fake classes for all dependencies (no MagicMock).
The deterministic FormulaReadabilityAnalyzer is used as-is (pure math).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from narrare.analysis.services.readability_service import ReadabilityService
from narrare_core.agents.readability_types import ReadabilityAgentOutput
from narrare_core.analysis.types import ReadabilityResult
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import NotFoundError
from tests.fakes import FakeChapterRepository, FakeModelRegistry, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos
from tests.unit.api.analysis._fakes import (
    FakeComposer,
    FakeReadabilityAgent,
    SpyInvocationPipeline,
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIG = ResolvedModelConfig(provider_name="anthropic", model_id="test-model")


def _make_service(
    content: str = "The cat sat on the mat. The dog ran to the park.",
    writing_language: str = "en",
    invocation_pipeline: InvocationPipeline | None = None,
    composer: FakeComposer | None = None,
) -> tuple[Any, Any, ReadabilityService]:
    novel = make_novel(writing_language=writing_language)
    ch = make_chapter(novel_id=novel.id, content=content)
    nr, cr = FakeNovelRepository(), FakeChapterRepository()
    seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
    svc = ReadabilityService(
        chapter_repo=cr,
        novel_repo=nr,
        model_registry=FakeModelRegistry(),
        model_config=_CONFIG,
        composer=composer or FakeComposer(),
        invocation_pipeline=invocation_pipeline,
    )
    return novel, ch, svc


def _inject(svc: ReadabilityService, agent: FakeReadabilityAgent) -> None:
    svc._get_agent = lambda system_prompt=None: agent  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# A. analyze — happy path
# ---------------------------------------------------------------------------


class TestReadabilityAnalyzeHappyPath:
    @pytest.mark.asyncio
    async def test_returns_list_of_results(self) -> None:
        novel, ch, svc = _make_service()
        _inject(svc, FakeReadabilityAgent())
        results = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], ReadabilityResult)

    @pytest.mark.asyncio
    async def test_agent_merges_sentence_analyses(self) -> None:
        novel, ch, svc = _make_service()
        fake = FakeReadabilityAgent(
            output=ReadabilityAgentOutput(
                problematic_sentences=[
                    {
                        "sentence": "Long complex sentence.",
                        "sentence_index": 0,
                        "issues": ["too_long"],
                        "readability_score": 0.3,
                        "suggestions": [{"alternative": "Shorter."}],
                    }
                ],
                overall_assessment="Needs work.",
            )
        )
        _inject(svc, fake)
        results = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert len(results[0].sentence_analyses) == 1
        assert results[0].sentence_analyses[0].issues == ["too_long"]
        assert results[0].overall_assessment == "Needs work."

    @pytest.mark.asyncio
    async def test_resolves_language_auto_from_novel(self) -> None:
        novel, ch, svc = _make_service(writing_language="de")
        fake = FakeReadabilityAgent()
        _inject(svc, fake)
        await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, language="auto"
        )
        assert fake.last_deps.language == "de"

    @pytest.mark.asyncio
    async def test_multiple_chapters_returns_in_order(self) -> None:
        novel = make_novel()
        ch1 = make_chapter(novel_id=novel.id, content="First chapter text here.")
        ch2 = make_chapter(novel_id=novel.id, content="Second chapter text here.")
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch1, ch2, novel_repo=nr, chapter_repo=cr)
        svc = ReadabilityService(
            chapter_repo=cr,
            novel_repo=nr,
            model_registry=FakeModelRegistry(),
            model_config=_CONFIG,
            composer=FakeComposer(),
        )
        _inject(svc, FakeReadabilityAgent())
        results = await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch1.id, ch2.id], user_id=novel.user_id
        )
        assert len(results) == 2


# ---------------------------------------------------------------------------
# B. analyze — error cases
# ---------------------------------------------------------------------------


class TestReadabilityAnalyzeErrors:
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
    async def test_agent_error_degrades_gracefully(self) -> None:
        novel, ch, svc = _make_service()
        fake = FakeReadabilityAgent(error=RuntimeError("LLM down"))
        _inject(svc, fake)
        results = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert len(results) == 1
        assert results[0].metrics.flesch_reading_ease > 0.0
        assert results[0].sentence_analyses == []
        assert results[0].overall_assessment is None


# ---------------------------------------------------------------------------
# C. analyze — empty content edge case
# ---------------------------------------------------------------------------


class TestReadabilityEmptyContent:
    @pytest.mark.asyncio
    async def test_empty_chapter_skips_agent(self) -> None:
        novel, ch, svc = _make_service(content="")
        fake = FakeReadabilityAgent()
        _inject(svc, fake)
        results = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert len(results) == 1
        assert not fake.run_called
        assert results[0].sentence_analyses == []

    @pytest.mark.asyncio
    async def test_whitespace_only_skips_agent(self) -> None:
        novel, ch, svc = _make_service(content="   \n  \t  ")
        fake = FakeReadabilityAgent()
        _inject(svc, fake)
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert not fake.run_called


# ---------------------------------------------------------------------------
# D. Invocation composition — verifies compose_invocation (ADR-048 Mode 1)
# ---------------------------------------------------------------------------


class TestInvocationComposition:
    """Verify the service routes through compose_invocation (Mode 1, composer-driven)."""

    @pytest.mark.asyncio
    async def test_compose_invocation_called_with_readability_feature_id(self) -> None:
        """The pipeline prepare/finalize are invoked with feature_id analysis_readability."""
        spy = SpyInvocationPipeline()
        novel, ch, svc = _make_service(invocation_pipeline=spy)
        _inject(svc, FakeReadabilityAgent())
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)

        assert len(spy.prepare_calls) == 1
        assert spy.prepare_calls[0].feature_id == "analysis_readability"
        assert len(spy.finalize_calls) == 1
        assert spy.finalize_calls[0].feature_id == "analysis_readability"


# ---------------------------------------------------------------------------
# E. Mode 1 prompt composition — composer-driven system prompt (ADR-048)
# ---------------------------------------------------------------------------


class TestMode1PromptComposition:
    """Mode 1: the composer-built system prompt reaches the agent."""

    @pytest.mark.asyncio
    async def test_composed_system_prompt_passed_to_agent(self) -> None:
        """The composer-built system prompt is handed to the agent constructor."""
        composer = FakeComposer(system="READABILITY-SYSTEM-PROMPT")
        novel, ch, svc = _make_service(composer=composer)
        captured: dict[str, object] = {}

        def spy_get_agent(system_prompt: str | None = None) -> FakeReadabilityAgent:
            captured["system_prompt"] = system_prompt
            return FakeReadabilityAgent()

        svc._get_agent = spy_get_agent  # type: ignore[method-assign]
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)

        assert captured["system_prompt"] == "READABILITY-SYSTEM-PROMPT"

    @pytest.mark.asyncio
    async def test_fallback_composes_directly_when_pipeline_none(self) -> None:
        """Without a pipeline, compose_invocation falls back to composer.build()."""
        composer = FakeComposer(system="FALLBACK-READABILITY")
        novel, ch, svc = _make_service(composer=composer)
        _inject(svc, FakeReadabilityAgent())
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)

        assert len(composer.build_calls) >= 1

    @pytest.mark.asyncio
    async def test_no_manual_injection_used(self) -> None:
        """Mode 1 never uses ManualInjectionDeclaration — composer drives the prompt."""
        import inspect

        from narrare.analysis.services import readability_service

        source = inspect.getsource(readability_service)
        assert "ManualInjectionDeclaration" not in source
        assert "manual_injection=" not in source
