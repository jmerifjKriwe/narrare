"""Tests for invocation evidence wiring in analysis services (ADR-040).

Verifies that each analysis service that makes LLM calls produces
invocation evidence when an ``InvocationPipeline`` (with a
``FakeEvidenceSink``) is wired, and that behavior is unchanged when
``invocation_pipeline=None`` (backward compatibility).

Services covered:
1. ReadabilityService — Phase 2 AI analysis
2. POVService — POVDetectionAgent

BetaReaderService coverage lives in the companion
``test_invocation_wiring_beta_reader.py`` (RULE-04 split when the
ADR-086 S4-beta wiring updates pushed this file past its hard limit).

See:
    ADR-040, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt

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


def _prepared_stub() -> PreparedModelCall:
    """Canned coherent triple for patched ``_prepare_agent`` (Task 6a-2).

    These tests stub the agent entirely, so the real prepare→run
    pass-through is verified by the dedicated wiring suites instead.
    """
    return PreparedModelCall(model=MagicMock(spec=object), model_settings=None, usage_limits=None)


def _static_resolution() -> StaticModelResolution:
    """ADR-086: pin the resolved model for direct service construction."""
    return StaticModelResolution(
        ResolvedModel(config=ResolvedModelConfig(provider_name="test", model_id="test-model"))
    )


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

        mock_composer = AsyncMock(spec=["build"])
        mock_composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user=""))

        service = ReadabilityService(
            chapter_repo=mock_chapter_repo,
            novel_repo=mock_novel_repo,
            model_registry=MagicMock(spec=["get_model", "prepare"]),
            model_resolution=_static_resolution(),
            composer=mock_composer,
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
            patch.object(service, "_prepare_agent") as mock_prepare_agent,
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
            mock_prepare_agent.return_value = (mock_agent, _prepared_stub())

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

        mock_composer = AsyncMock(spec=["build"])
        mock_composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user=""))

        service = POVService(
            chapter_repo=mock_chapter_repo,
            novel_repo=mock_novel_repo,
            model_registry=MagicMock(spec=["get_model", "prepare"]),
            model_resolution=_static_resolution(),
            composer=mock_composer,
            invocation_pipeline=pipeline,
        )

        with (
            patch.object(service, "_prepare_agent") as mock_prepare_agent,
            patch("narrare.analysis.services.pov_service.map_output_to_result") as mock_map,
        ):
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=MagicMock(spec=["output"]))
            mock_prepare_agent.return_value = (mock_agent, _prepared_stub())

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
