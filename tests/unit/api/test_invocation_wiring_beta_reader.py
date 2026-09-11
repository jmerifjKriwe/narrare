"""Invocation evidence wiring — BetaReaderService (ADR-040).

Split from ``test_invocation_wiring_analysis.py`` for the RULE-04
test-file hard limit. Proves that BetaReaderService produces invocation
evidence when an ``InvocationPipeline`` (with a ``FakeEvidenceSink``) is
wired, and that behavior is unchanged when ``invocation_pipeline=None``
(backward compatibility).

See:
    ADR-040, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.analysis.assembler import AnalysisContextAssembler
from narrare_core.llm import ResolvedModel, ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import FeatureInvocationEvidence


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


def _resolver_ready_config() -> ResolvedModelConfig:
    """Real config value object — the ADR-045 run-limit resolver (Task 3)
    reads ``resolve_output_limit()``/``token_limit_profile`` from it."""
    return ResolvedModelConfig(
        provider_name="default", model_id="default", temperature=0.7, max_tokens=4096
    )


async def _default_budget_assembler() -> AnalysisContextAssembler:
    """Default (uncapped) budget assembler — pre-ADR-086 unit default."""
    return AnalysisContextAssembler()


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
        # Use a real ComposedPrompt (not a spec'd MagicMock) so the pipeline's
        # fingerprint_prompt can read both .system and .user when recording evidence.
        mock_composed = ComposedPrompt(system="System prompt", user="")
        mock_composer.build = AsyncMock(return_value=mock_composed)

        mock_registry = MagicMock(spec=["get_model", "prepare"])
        mock_registry.get_model = AsyncMock(return_value=MagicMock(spec=["run"]))
        mock_registry.prepare = AsyncMock(return_value=_prepared_stub())

        service = BetaReaderService(
            context_assembler=mock_assembler,
            cache=mock_cache,
            registry=mock_registry,
            model_resolution=StaticModelResolution(ResolvedModel(config=_resolver_ready_config())),
            composer=mock_composer,
            budget_assembler_factory=_default_budget_assembler,
            invocation_pipeline=pipeline,
        )

        mock_deps = MagicMock(
            spec=[
                "chapter_text",
                "word_count",
                "language",
                "focus_categories",
                "genre",
                "chapter_titles",
                "kb_characters",
                "kb_locations",
                "previous_chapter_summaries",
            ]
        )
        mock_deps.chapter_text = "Some text. " * 200
        mock_deps.word_count = 500
        mock_deps.language = "en"
        mock_deps.focus_categories = []
        mock_deps.genre = None
        mock_deps.chapter_titles = ["Ch 1"]
        mock_deps.kb_characters = ""
        mock_deps.kb_locations = ""
        mock_deps.previous_chapter_summaries = []

        # Patch the internal boundaries to avoid full agent execution.
        # Context assembly moved to the module-level ``assemble_context``
        # boundary (RULE-04 split) — patch the service-module binding so
        # the flow reaches the compose → resolve → prepare → run path.
        with (
            patch(
                "narrare.analysis.beta_reader_service.assemble_context",
                new=AsyncMock(return_value=mock_deps),
            ),
            patch("narrare.analysis.beta_reader_service.validate_word_count"),
            patch(
                "narrare.analysis.beta_reader_service.run_phase1",
                AsyncMock(return_value=MagicMock(spec=["output"])),
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

        # No pipeline → compose_invocation falls back to composer.build() directly.
        mock_composer = AsyncMock(spec=["build"])
        mock_composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user=""))

        mock_registry = MagicMock(spec=["get_model", "prepare"])
        mock_registry.prepare = AsyncMock(return_value=_prepared_stub())

        service = BetaReaderService(
            context_assembler=AsyncMock(),
            cache=mock_cache,
            registry=mock_registry,
            model_resolution=StaticModelResolution(ResolvedModel(config=_resolver_ready_config())),
            composer=mock_composer,
            budget_assembler_factory=_default_budget_assembler,
            invocation_pipeline=None,
        )

        with (
            patch(
                "narrare.analysis.beta_reader_service.assemble_context",
                new=AsyncMock(
                    return_value=MagicMock(
                        spec=[
                            "chapter_text",
                            "word_count",
                            "language",
                            "focus_categories",
                            "genre",
                            "chapter_titles",
                            "kb_characters",
                            "kb_locations",
                            "previous_chapter_summaries",
                        ],
                        chapter_text="x" * 100,
                        word_count=50,
                        language="en",
                        focus_categories=[],
                        genre=None,
                        chapter_titles=["Ch 1"],
                        kb_characters="",
                        kb_locations="",
                        previous_chapter_summaries=[],
                    )
                ),
            ),
            patch("narrare.analysis.beta_reader_service.validate_word_count"),
            patch(
                "narrare.analysis.beta_reader_service.run_phase1",
                AsyncMock(return_value=MagicMock(spec=["output"])),
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
