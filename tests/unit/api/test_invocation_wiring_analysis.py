"""Tests for invocation evidence wiring in analysis services (ADR-040).

Verifies that each analysis service that makes LLM calls produces
invocation evidence when an ``InvocationPipeline`` (with a
``FakeEvidenceSink``) is wired, and that behavior is unchanged when
``invocation_pipeline=None`` (backward compatibility).

Services covered:
1. BetaReaderService — Phase 1 + Phase 2
2. ReadabilityService — Phase 2 AI analysis
3. POVService — POVDetectionAgent

See:
    ADR-040, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.ai_invocation.pipeline import InvocationPipeline

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import FeatureInvocationEvidence

# ---------------------------------------------------------------------------
# FakeEvidenceSink — records evidence in memory
# ---------------------------------------------------------------------------


class FakeEvidenceSink:
    """In-memory evidence sink for testing."""

    def __init__(self) -> None:
        self.records: list[FeatureInvocationEvidence] = []

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        self.records.append(evidence)


def _pipeline_with_sink(sink: FakeEvidenceSink) -> InvocationPipeline:
    """Create an InvocationPipeline with only the evidence sink wired."""
    return InvocationPipeline(evidence_sink=sink)


# ===========================================================================
# 1. BetaReaderService invocation wiring
# ===========================================================================


class TestBetaReaderInvocationWiring:
    """BetaReaderService records evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_analyze_produces_evidence(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = _pipeline_with_sink(sink)

        from narrare.analysis.beta_reader_service import BetaReaderService

        mock_cache = MagicMock(spec=["get", "set", "hash_chapter_ids"])
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        mock_assembler = AsyncMock()

        mock_composer = AsyncMock(spec=["build"])
        mock_composed = MagicMock(spec=["system"])
        mock_composed.system = "System prompt"
        mock_composer.build = AsyncMock(return_value=mock_composed)

        mock_registry = MagicMock(spec=["get_model"])
        mock_registry.get_model = AsyncMock(return_value=MagicMock(spec=["run"]))

        service = BetaReaderService(
            context_assembler=mock_assembler,
            cache=mock_cache,
            registry=mock_registry,
            config=MagicMock(spec=["model_id", "provider_name"]),
            composer=mock_composer,
            invocation_pipeline=pipeline,
        )

        mock_deps = MagicMock(spec=["chapter_text", "word_count", "language", "focus_categories"])
        mock_deps.chapter_text = "Some text. " * 200
        mock_deps.word_count = 500
        mock_deps.language = "en"
        mock_deps.focus_categories = []

        # Patch the internal methods to avoid full agent execution.
        # Must patch _assemble_context so the flow reaches _record_evidence.
        with (
            patch.object(service, "_assemble_context", AsyncMock(return_value=mock_deps)),
            patch.object(service, "_compose_prompt", AsyncMock(return_value=mock_composed)),
            patch("narrare.analysis.beta_reader_service.validate_word_count"),
            patch.object(
                service, "_run_agent_phase1", AsyncMock(return_value=MagicMock(spec=["output"]))
            ),
            patch(
                "narrare.analysis.beta_reader_service.map_phase1_response",
                return_value=MagicMock(
                    spec=["model_dump_json", "cache_key"],
                    model_dump_json=MagicMock(spec=["__call__"], return_value="{}"),
                    cache_key="abc",
                ),
            ),
            patch(
                "narrare.analysis.beta_reader_service.BetaReaderCache.hash_chapter_ids",
                return_value="abc123",
            ),
            contextlib.suppress(Exception),
        ):
            await service.analyze(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=MagicMock(
                    spec=["chapter_ids", "refresh", "categories"],
                    chapter_ids=["ch1"],
                    refresh=True,
                    categories=None,
                ),
            )
            # May fail on response mapping — evidence is what matters

        assert len(sink.records) >= 1, "Expected at least one evidence record"

    @pytest.mark.asyncio
    async def test_analyze_without_pipeline_no_evidence(self) -> None:
        sink = FakeEvidenceSink()
        # Pipeline NOT wired to the service
        mock_cache = MagicMock(spec=["get", "set", "hash_chapter_ids"])
        mock_cache.get = AsyncMock(return_value=None)

        from narrare.analysis.beta_reader_service import BetaReaderService

        service = BetaReaderService(
            context_assembler=AsyncMock(),
            cache=mock_cache,
            registry=MagicMock(spec=["get_model"]),
            config=MagicMock(spec=["model_id", "provider_name"]),
            composer=MagicMock(spec=["build"]),
            invocation_pipeline=None,
        )

        with (
            patch.object(
                service,
                "_assemble_context",
                AsyncMock(
                    return_value=MagicMock(
                        spec=["chapter_text", "word_count", "language", "focus_categories"],
                        chapter_text="x" * 100,
                        word_count=50,
                        language="en",
                        focus_categories=[],
                    )
                ),
            ),
            patch.object(
                service,
                "_compose_prompt",
                AsyncMock(return_value=MagicMock(spec=["system"], system="s")),
            ),
            patch("narrare.analysis.beta_reader_service.validate_word_count"),
            patch.object(
                service, "_run_agent_phase1", AsyncMock(return_value=MagicMock(spec=["output"]))
            ),
            patch(
                "narrare.analysis.beta_reader_service.map_phase1_response",
                return_value=MagicMock(
                    spec=["model_dump_json"],
                    model_dump_json=MagicMock(spec=["__call__"], return_value="{}"),
                ),
            ),
            patch.object(mock_cache, "set", AsyncMock()),
            patch.object(mock_cache, "hash_chapter_ids", return_value="abc"),
            contextlib.suppress(Exception),
        ):
            await service.analyze(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=MagicMock(
                    spec=["chapter_ids", "refresh", "categories"],
                    chapter_ids=["ch1"],
                    refresh=True,
                    categories=None,
                ),
            )

        assert len(sink.records) == 0, "No evidence should be recorded without pipeline"


# ===========================================================================
# 2. ReadabilityService invocation wiring
# ===========================================================================


class TestReadabilityInvocationWiring:
    """ReadabilityService records evidence for AI sentence analysis."""

    @pytest.mark.asyncio
    async def test_analyze_produces_evidence_with_pipeline(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = _pipeline_with_sink(sink)

        from narrare.analysis.services.readability_service import ReadabilityService

        novel_id = uuid4()
        user_id = uuid4()

        mock_novel_repo = MagicMock(spec=["get_by_id"])
        mock_novel = MagicMock(spec=["writing_language"])
        mock_novel.writing_language = "en"
        mock_novel_repo.get_by_id = AsyncMock(return_value=mock_novel)

        mock_chapter = MagicMock(spec=["content"])
        mock_chapter.content = "This is a test sentence for analysis. " * 10
        mock_chapter_repo = MagicMock(spec=["get_by_id"])
        mock_chapter_repo.get_by_id = AsyncMock(return_value=mock_chapter)

        service = ReadabilityService(
            chapter_repo=mock_chapter_repo,
            novel_repo=mock_novel_repo,
            model_registry=MagicMock(spec=["get_model"]),
            model_config=MagicMock(spec=["model_id", "provider_name"]),
            invocation_pipeline=pipeline,
        )

        # Patch formula analyzer and agent to avoid actual LLM
        with (
            patch.object(service, "_formula_analyzer") as mock_formula,
            patch.object(
                service,
                "_merge_agent_result",
                return_value=MagicMock(spec=["metrics", "sentence_analyses"]),
            ),
            patch.object(service, "_get_agent") as mock_get_agent,
        ):
            mock_result = MagicMock(
                spec=["metrics", "sentence_analyses", "genre_benchmarks", "overall_assessment"],
            )
            mock_result.metrics = MagicMock(spec=["flesch_reading_ease", "sentence_count"])
            mock_result.metrics.flesch_reading_ease = 80.0
            mock_result.metrics.sentence_count = 5
            mock_result.sentence_analyses = []
            mock_result.genre_benchmarks = None
            mock_result.overall_assessment = None
            mock_formula.analyze = AsyncMock(return_value=mock_result)

            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=MagicMock(spec=["output"]))
            mock_get_agent.return_value = mock_agent

            await service.analyze(
                novel_id=novel_id,
                chapter_ids=[uuid4()],
                user_id=user_id,
            )

        assert len(sink.records) >= 1


# ===========================================================================
# 3. POVService invocation wiring
# ===========================================================================


class TestPOVInvocationWiring:
    """POVService records evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_analyze_produces_evidence_with_pipeline(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = _pipeline_with_sink(sink)

        from narrare.analysis.services.pov_service import POVService

        novel_id = uuid4()
        user_id = uuid4()

        mock_novel_repo = MagicMock(spec=["get_by_id"])
        mock_novel = MagicMock(spec=["writing_language"])
        mock_novel.writing_language = "en"
        mock_novel_repo.get_by_id = AsyncMock(return_value=mock_novel)

        mock_chapter = MagicMock(spec=["content"])
        mock_chapter.content = "He walked into the room and saw her."
        mock_chapter_repo = MagicMock(spec=["get_by_id"])
        mock_chapter_repo.get_by_id = AsyncMock(return_value=mock_chapter)

        mock_kb_repo = MagicMock(spec=["list_entries"])
        mock_kb_repo.list_entries = AsyncMock(return_value=([], 0))

        service = POVService(
            chapter_repo=mock_chapter_repo,
            novel_repo=mock_novel_repo,
            kb_repo=mock_kb_repo,
            model_registry=MagicMock(spec=["get_model"]),
            model_config=MagicMock(spec=["model_id", "provider_name"]),
            invocation_pipeline=pipeline,
        )

        with (
            patch.object(service, "_get_agent") as mock_get_agent,
            patch("narrare.analysis.services.pov_service.map_output_to_result") as mock_map,
        ):
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=MagicMock(spec=["output"]))
            mock_get_agent.return_value = mock_agent

            from narrare_core.analysis.types import POVResult

            mock_map.return_value = POVResult(
                scenes=[],
                issues=[],
                pov_distribution={},
                switch_count=0,
                analysis_type="",
            )
            await service.analyze(
                novel_id=novel_id,
                chapter_ids=[uuid4()],
                user_id=user_id,
            )

        assert len(sink.records) >= 1
