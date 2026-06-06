"""Tests for invocation wiring across writing sub-pipelines (part 1).

Verifies that each sub-pipeline produces invocation evidence when an
``InvocationPipeline`` (with a ``FakeEvidenceSink``) is wired into
``WritingPipeline``, and that behavior is unchanged when
``invocation_pipeline=None``.

Sub-pipelines covered here:
1. ``stream_extend``       — pipeline_extend.py
2. ``stream_rewrite``      — pipeline_rewrite.py
3. ``stream_coauthor``     — pipeline_coauthor.py

See: ADR-040 Decision 4, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from tests.unit.core.writing._invocation_helpers import (
    CONFIG,
    FakeEvidenceSink,
    _collect,
    _ctx,
    _make_pipeline,
    _mock_pipeline_with_sink,
    _req,
    _setup_stream,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_registry() -> Any:
    return MagicMock(spec=["stream", "run"])


@pytest.fixture()
def mock_composer() -> Any:
    comp = MagicMock(spec=PromptComposer)
    comp.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))
    return comp


@pytest.fixture()
def mock_assembler() -> Any:
    asm = MagicMock(spec=WritingContextAssembler)
    asm.assemble = AsyncMock(return_value=_ctx())
    return asm


@pytest.fixture()
def mock_processor() -> Any:
    proc = MagicMock(spec=DraftProcessor)
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return proc


# ===========================================================================
# 1. stream_extend — pipeline_extend.py
# ===========================================================================


class TestExtendInvocationWiring:
    """stream_extend produces evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_with_pipeline_produces_evidence(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Extended text.")

        chunks = await _collect(
            pipeline.generate(_req(GenerationMode.EXTEND), config=CONFIG),
        )
        assert any(c.is_final for c in chunks)
        assert len(sink.records) == 1
        assert sink.records[0].feature_id.startswith("writing_")

    @pytest.mark.asyncio
    async def test_without_pipeline_behaves_identically(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=None,
        )
        _setup_stream(mock_registry, "Extended text.")

        chunks = await _collect(
            pipeline.generate(_req(GenerationMode.EXTEND), config=CONFIG),
        )
        assert any(c.is_final for c in chunks)
        # No evidence sink — but no errors either
        assert mock_composer.build.call_count == 1
        assert mock_registry.stream.call_count == 1

    @pytest.mark.asyncio
    async def test_evidence_has_correct_intent(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Text.")

        await _collect(
            pipeline.generate(_req(GenerationMode.EXTEND), config=CONFIG),
        )
        assert sink.records[0].feature_id == "writing_extend"


# ===========================================================================
# 2. stream_rewrite — pipeline_rewrite.py
# ===========================================================================


class TestRewriteInvocationWiring:
    """stream_rewrite produces evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_with_pipeline_produces_evidence(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Rewritten text.")

        chunks = await _collect(
            pipeline.generate(
                _req(GenerationMode.REWRITE),
                config=CONFIG,
                selection_text="Original text.",
            ),
        )
        assert any(c.is_final for c in chunks)
        assert len(sink.records) == 1

    @pytest.mark.asyncio
    async def test_without_pipeline_behaves_identically(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=None,
        )
        _setup_stream(mock_registry, "Rewritten text.")

        chunks = await _collect(
            pipeline.generate(
                _req(GenerationMode.REWRITE),
                config=CONFIG,
                selection_text="Original text.",
            ),
        )
        assert any(c.is_final for c in chunks)
        assert mock_composer.build.call_count == 1

    @pytest.mark.asyncio
    async def test_evidence_has_correct_intent(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Text.")

        await _collect(
            pipeline.generate(
                _req(GenerationMode.REWRITE),
                config=CONFIG,
                selection_text="Original.",
            ),
        )
        assert sink.records[0].feature_id == "writing_rewrite"


# ===========================================================================
# 3. stream_coauthor — pipeline_coauthor.py
# ===========================================================================


class TestCoauthorInvocationWiring:
    """stream_coauthor produces evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_with_pipeline_produces_evidence(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Improved text.")

        chunks = await _collect(
            pipeline.generate(
                _req(GenerationMode.CO_AUTHOR),
                config=CONFIG,
                selection_text="Original text.",
                co_author_focus=["dialogue"],
            ),
        )
        assert any(c.is_final for c in chunks)
        assert len(sink.records) == 1

    @pytest.mark.asyncio
    async def test_without_pipeline_behaves_identically(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=None,
        )
        _setup_stream(mock_registry, "Improved text.")

        chunks = await _collect(
            pipeline.generate(
                _req(GenerationMode.CO_AUTHOR),
                config=CONFIG,
                selection_text="Original text.",
                co_author_focus=["word_choice"],
            ),
        )
        assert any(c.is_final for c in chunks)
        assert mock_composer.build.call_count == 1

    @pytest.mark.asyncio
    async def test_evidence_has_correct_intent(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Text.")

        await _collect(
            pipeline.generate(
                _req(GenerationMode.CO_AUTHOR),
                config=CONFIG,
                selection_text="Original.",
                co_author_focus=["sentence"],
            ),
        )
        assert sink.records[0].feature_id == "writing_co_author"
