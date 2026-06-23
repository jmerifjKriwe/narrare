"""Style-variant injection tests for the rewrite pipeline (CR-AUFG-07-22).

Verifies that the ``style_variant`` parameter threads through
``WritingPipeline.generate()`` → ``stream_rewrite()`` and lands in the
prompt context ``extra`` as ``style_variant_instructions``:

- When a variant is set, the instruction text is populated.
- When ``None`` (default), an empty string is injected (backward compatible —
  the template renders nothing).
- Each of the 6 variants produces a distinct instruction.

This file is intentionally self-contained (helpers + fixtures) so that
``test_rewrite_pipeline.py`` stays within the RULE-04 line limit.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline
from narrare_core.writing.style_variants import StyleVariant

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model", max_tokens=2000)
USAGE = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


def _req(**kw: Any) -> GenerationRequest:
    defaults: dict[str, Any] = {
        "chapter_id": uuid4(),
        "project_id": uuid4(),
        "user_id": uuid4(),
        "mode": GenerationMode.REWRITE,
    }
    defaults.update(kw)
    return GenerationRequest(**defaults)


def _ctx(**kw: Any) -> WritingContext:
    defaults: dict[str, Any] = {
        "chapter_content": "",
        "project_title": "Test Novel",
        "genre": "fantasy",
        "language": "en",
        "tone": "balanced",
        "writing_language": "English",
    }
    defaults.update(kw)
    return WritingContext(**defaults)


async def _collect(gen: Any) -> list[StreamChunk]:
    out: list[StreamChunk] = []
    async for c in gen:
        out.append(c)
    return out


async def _stream(*chunks: StreamChunk):  # type: ignore[no-untyped-def]
    for c in chunks:
        yield c


def _setup_stream(mock_registry: Any, *texts: str) -> None:
    """Wire mock_registry.stream to yield text chunks + final chunk."""
    chunks = [StreamChunk(text=t) for t in texts]
    chunks.append(StreamChunk(text="", is_final=True, usage=USAGE))
    mock_registry.stream = MagicMock(spec=[], return_value=_stream(*chunks))


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


@pytest.fixture()
def pipeline(
    mock_registry: Any, mock_composer: Any, mock_assembler: Any, mock_processor: Any
) -> WritingPipeline:
    return WritingPipeline(
        registry=mock_registry,
        composer=mock_composer,
        context_assembler=mock_assembler,
        draft_processor=mock_processor,
    )


# ---------------------------------------------------------------------------
# Style-variant injection (CR-AUFG-07-22)
# ---------------------------------------------------------------------------


class TestStyleVariantInjection:
    @pytest.mark.asyncio
    async def test_style_variant_instructions_in_extra(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        """When style_variant is set, style_variant_instructions appears in extra."""
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text to regenerate.",
                style_variant=StyleVariant.LEANER,
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        assert "style_variant_instructions" in ctx.extra
        assert "leaner" in ctx.extra["style_variant_instructions"].lower()

    @pytest.mark.asyncio
    async def test_no_style_variant_yields_empty_string(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        """When style_variant is None, style_variant_instructions is empty string."""
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        assert ctx.extra["style_variant_instructions"] == ""

    @pytest.mark.asyncio
    async def test_each_variant_produces_distinct_instruction(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        """Different variants inject different instruction text."""
        instructions_seen: set[str] = set()
        for variant in StyleVariant:
            _setup_stream(mock_registry)
            await _collect(
                pipeline.generate(
                    _req(),
                    config=CONFIG,
                    selection_text="Text.",
                    style_variant=variant,
                )
            )
            ctx = mock_composer.build.call_args.args[1]
            instructions_seen.add(ctx.extra["style_variant_instructions"])
        assert len(instructions_seen) == len(list(StyleVariant))
