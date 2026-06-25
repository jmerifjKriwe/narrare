"""Tests for invocation evidence wiring in KB services (ADR-040).

Verifies that each KB service that makes LLM calls produces
invocation evidence when an ``InvocationPipeline`` (with a
``FakeEvidenceSink``) is wired, and that behavior is unchanged when
``invocation_pipeline=None`` (backward compatibility).

Services covered:
1. ExtractionService — ExtractionAgent
2. KBConsistencyService — LLM phases
3. KBImproveService — KBImproveAnalyzer
4. WorldbuildingService — WorldbuildingAnalyzer
5. KBAssistService — KBAssistAgent
6. KBMergeService — KBMergeAgent

See:
    ADR-040, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

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
# 1. ExtractionService invocation wiring
# ===========================================================================


class TestExtractionInvocationWiring:
    """ExtractionService records evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_extract_produces_evidence_with_pipeline(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = _pipeline_with_sink(sink)

        from narrare.kb.extraction_service import ExtractionService

        novel_id = uuid4()
        chapter_id = uuid4()
        user_id = uuid4()

        mock_chapter = MagicMock(spec=["content", "title"])
        mock_chapter.content = "Alice met Bob at the tavern."
        mock_chapter.title = "Chapter 1"
        mock_chapter_repo = MagicMock(spec=["get_by_id"])
        mock_chapter_repo.get_by_id = AsyncMock(return_value=mock_chapter)

        mock_kb_repo = MagicMock(spec=["list_entries"])
        mock_kb_repo.list_entries = AsyncMock(return_value=([], 0))

        mock_registry = MagicMock(spec=["get_model"])
        mock_registry.get_model = AsyncMock(return_value=MagicMock(spec=["run"]))

        from narrare_core.prompts.composer import ComposedPrompt

        mock_composer = MagicMock(spec=["build"])
        mock_composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))

        service = ExtractionService(
            registry=mock_registry,
            config=MagicMock(spec=["model_id", "provider_name"]),
            chapter_repo=mock_chapter_repo,
            kb_repo=mock_kb_repo,
            composer=mock_composer,
            invocation_pipeline=pipeline,
        )

        mock_output = MagicMock(spec=["results", "analysis_notes"])
        mock_output.results = []
        mock_output.analysis_notes = ""

        with (
            patch("narrare.kb.extraction_service.ExtractionAgent") as mock_agent_cls,
            patch.object(service, "_get_existing_entity_names", AsyncMock(return_value=[])),
        ):
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=mock_output)
            mock_agent_cls.return_value = mock_agent

            result = await service.extract_from_chapter(
                novel_id=novel_id,
                chapter_id=chapter_id,
                user_id=user_id,
            )

        assert len(sink.records) >= 1
        assert result is not None


# ===========================================================================
# 2. KBConsistencyService invocation wiring
# ===========================================================================


class TestConsistencyInvocationWiring:
    """KBConsistencyService records evidence for LLM phases."""

    @pytest.mark.asyncio
    async def test_check_produces_evidence_with_pipeline(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = _pipeline_with_sink(sink)

        from narrare.kb.consistency_service import KBConsistencyService

        novel_id = uuid4()

        mock_analyzer = MagicMock(spec=["analyze_entries"])
        mock_analyzer.analyze_entries = AsyncMock(return_value=([], 0))

        service = KBConsistencyService(
            analyzer=mock_analyzer,
            asymmetry_checker=MagicMock(spec=["check"]),
            worldbuilding_analyzer=MagicMock(spec=["analyze"]),
            kb_repo=MagicMock(spec=["list_entries"]),
            rel_repo=MagicMock(spec=["get_by_id"]),
            cache=MagicMock(spec=["get", "set", "hash_entity_types"]),
            invocation_pipeline=pipeline,
        )

        mock_cache = service._cache
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.hash_entity_types = MagicMock(spec=["__call__"], return_value="hash")
        mock_cache.set = AsyncMock()

        mock_asym = service._asymmetry_checker
        mock_asym.check = AsyncMock(return_value=[])

        # Patch _run_cross_entity to avoid complex setup
        with patch.object(service, "_run_cross_entity", AsyncMock(return_value=[])):
            from narrare.kb.consistency_contracts import ConsistencyCheckRequest

            request = ConsistencyCheckRequest(
                include_asymmetry=True,
                include_entry_internal=True,
                include_cross_entity=False,
            )
            _result = await service.check(novel_id=novel_id, request=request)

        assert len(sink.records) >= 1


# ===========================================================================
# 3. KBImproveService invocation wiring
# ===========================================================================


class TestImproveInvocationWiring:
    """KBImproveService delegates to analyzer (evidence recorded there)."""

    @pytest.mark.asyncio
    async def test_analyze_delegates_to_analyzer(self) -> None:
        from narrare.kb.improve_service import KBImproveService

        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["suggestions"]))

        service = KBImproveService(
            analyzer=mock_analyzer,
            kb_repo=MagicMock(spec=["get_by_id"]),
            kb_service=MagicMock(spec=["get"]),
            rel_repo=MagicMock(spec=["get_by_id"]),
        )

        await service.analyze(novel_id=uuid4(), entry_id=uuid4())

        # Evidence recording has moved to the analyzer (ADR-048 Mode 1).
        # The service is now a thin delegation layer.
        mock_analyzer.analyze.assert_awaited_once()


# ===========================================================================
# 4. WorldbuildingService invocation wiring
# ===========================================================================


class TestWorldbuildingInvocationWiring:
    """WorldbuildingService delegates to analyzer (evidence recorded there)."""

    @pytest.mark.asyncio
    async def test_analyze_delegates_to_analyzer(self) -> None:
        from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisRequest
        from narrare.kb.worldbuilding_service import WorldbuildingService

        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["connections"]))

        service = WorldbuildingService(
            analyzer=mock_analyzer,
            rel_repo=MagicMock(spec=["get_by_id"]),
            cache=MagicMock(spec=["get", "set"]),
        )

        request = WorldbuildingAnalysisRequest()
        await service.analyze(novel_id=uuid4(), request=request)

        # Evidence recording has moved to the analyzer (ADR-048 Mode 1).
        # The service is now a thin delegation layer.
        mock_analyzer.analyze.assert_awaited_once()


# ===========================================================================
# 5. KBAssistService invocation wiring
# ===========================================================================


class TestAssistInvocationWiring:
    """KBAssistService records evidence via compose_invocation (Mode 1)."""

    @pytest.mark.asyncio
    async def test_run_agent_produces_evidence(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = _pipeline_with_sink(sink)

        from narrare.kb.assist_service import KBAssistService
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.composer import ComposedPrompt

        mock_proactive = MagicMock(spec=["suggest"])
        mock_proactive.suggest = AsyncMock(return_value=[])

        mock_composer = MagicMock(spec=["build"])
        mock_composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))

        service = KBAssistService(
            registry=MagicMock(spec=["get_model"]),
            config=MagicMock(spec=["model_id", "provider_name"]),
            proactive_context=mock_proactive,
            prompt_composer=mock_composer,
            invocation_pipeline=pipeline,
        )

        mock_output = MagicMock(spec=["text"])
        with (
            patch("narrare.kb.assist_service.KBAssistAgent") as mock_agent_cls,
            patch.object(service, "_get_model", AsyncMock(return_value=MagicMock(spec=["run"]))),
        ):
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=mock_output)
            mock_agent_cls.return_value = mock_agent

            _result = await service._run_agent(
                user_prompt="Test prompt",
                deps=MagicMock(spec=["language", "genre"]),
                intent=LLMIntent.KB_INTERVIEW,
                entity_type="character",
                existing_fields={},
            )

        assert len(sink.records) >= 1


# ===========================================================================
# 6. KBMergeService invocation wiring
# ===========================================================================


class TestMergeInvocationWiring:
    """KBMergeService records evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_analyze_produces_evidence_with_pipeline(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = _pipeline_with_sink(sink)

        from narrare.kb.merge_service import KBMergeService

        mock_novel = MagicMock(spec=["title", "genre", "writing_language"])
        mock_novel.title = "Test Novel"
        mock_novel.genre = "fantasy"
        mock_novel.writing_language = "en"
        mock_novel_repo = MagicMock(spec=["get_by_id"])
        mock_novel_repo.get_by_id = AsyncMock(return_value=mock_novel)

        mock_registry = MagicMock(spec=["get_model"])
        mock_registry.get_model = AsyncMock(return_value=MagicMock(spec=["run"]))

        from narrare_core.prompts.composer import ComposedPrompt

        mock_composer = MagicMock(spec=["build"])
        mock_composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))

        service = KBMergeService(
            novel_repo=mock_novel_repo,
            model_registry=mock_registry,
            model_config=MagicMock(spec=["model_id", "provider_name"]),
            composer=mock_composer,
            invocation_pipeline=pipeline,
        )

        mock_output = MagicMock(spec=["merge_decisions", "overall_notes"])
        mock_output.merge_decisions = []
        mock_output.overall_notes = "No merge candidates found."

        # KBMergeAgent is lazy-imported inside the method body, so patch
        # the source module rather than the service module namespace.
        with patch("narrare_core.agents.merge_agent.KBMergeAgent") as mock_agent_cls:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=mock_output)
            mock_agent_cls.return_value = mock_agent

            from narrare.kb.schemas_merge import MergeRequest

            request = MergeRequest(
                entity_type="character",
                candidate_pairs=[{"name_a": "Alice", "name_b": "Alis"}],
            )
            _result = await service.analyze_merge_candidates(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=request,
            )

        assert len(sink.records) >= 1


# ===========================================================================
# Backward compatibility — no pipeline = no crash
# ===========================================================================


class TestBackwardCompatibility:
    """KB services work correctly when invocation_pipeline is None."""

    @pytest.mark.asyncio
    async def test_improve_service_without_pipeline(self) -> None:
        """KBImproveService works without invocation_pipeline."""
        from narrare.kb.improve_service import KBImproveService

        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["suggestions"]))

        service = KBImproveService(
            analyzer=mock_analyzer,
            kb_repo=MagicMock(spec=["get_by_id"]),
            kb_service=MagicMock(spec=["get"]),
            rel_repo=MagicMock(spec=["get_by_id"]),
            invocation_pipeline=None,
        )

        result = await service.analyze(novel_id=uuid4(), entry_id=uuid4())
        assert result is not None

    @pytest.mark.asyncio
    async def test_worldbuilding_service_without_pipeline(self) -> None:
        """WorldbuildingService works without invocation_pipeline."""
        from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisRequest
        from narrare.kb.worldbuilding_service import WorldbuildingService

        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["connections"]))

        service = WorldbuildingService(
            analyzer=mock_analyzer,
            rel_repo=MagicMock(spec=["get_by_id"]),
            cache=MagicMock(spec=["get", "set"]),
            invocation_pipeline=None,
        )

        result = await service.analyze(novel_id=uuid4(), request=WorldbuildingAnalysisRequest())
        assert result is not None
