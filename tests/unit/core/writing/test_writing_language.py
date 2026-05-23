"""Tests for writing_language migration.

Task 2.6: WritingContext.to_prompt_variables() includes writing_language.
Task 3.5: WritingPipeline._build_prompt_context() injects writing_language.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import (
    GenerationRequest,
    WritingContext,
)
from narrare_core.writing.pipeline import WritingPipeline


def _request(
    writing_language: str = "en",
) -> GenerationRequest:
    return GenerationRequest(
        chapter_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        mode=GenerationMode.FULL_DRAFT,
        writing_language=writing_language,
    )


def _default_context(writing_language: str = "en") -> WritingContext:
    return WritingContext(
        chapter_content="Previous content.",
        project_title="Test Novel",
        genre="fantasy",
        language="en",
        writing_language=writing_language,
        tone="balanced",
    )


class TestWritingLanguageInPromptVariables:
    """Task 2.6: WritingContext.to_prompt_variables includes writing_language."""

    def test_writing_language_in_prompt_variables(self) -> None:
        ctx = WritingContext(writing_language="Schweizerdeutsch")
        vars = ctx.to_prompt_variables()
        assert vars["writing_language"] == "Schweizerdeutsch"

    def test_writing_language_default(self) -> None:
        ctx = WritingContext()
        vars = ctx.to_prompt_variables()
        assert vars["writing_language"] == "en"

    def test_writing_language_does_not_contain_language_key(self) -> None:
        ctx = WritingContext(writing_language="Klingonisch")
        vars = ctx.to_prompt_variables()
        # language was renamed to writing_language in to_prompt_variables
        assert "language" not in vars


class TestWritingLanguageInPipelineContext:
    """Task 3.5: Pipeline _build_prompt_context injects writing_language."""

    def test_writing_language_in_prompt_context(
        self,
    ) -> None:
        pipeline = _make_pipeline()
        context = _default_context(writing_language="Deutsch")
        request = _request(writing_language="Deutsch")
        prompt_ctx = pipeline._build_prompt_context(request, context)
        assert prompt_ctx.writing_language == "Deutsch"
        assert prompt_ctx.extra.get("writing_language") == "Deutsch"

    def test_writing_language_empty_default(self) -> None:
        pipeline = _make_pipeline()
        context = WritingContext()
        request = _request(writing_language="en")
        prompt_ctx = pipeline._build_prompt_context(request, context)
        assert prompt_ctx.writing_language == "en"
        assert prompt_ctx.extra.get("writing_language") == "en"

    def test_writing_language_in_prompt_context_separate_from_language(
        self,
    ) -> None:
        """Verify language (prompt file selection) and writing_language are separate."""
        pipeline = _make_pipeline()
        context = WritingContext(
            language="de",
            writing_language="Schweizerdeutsch",
        )
        request = _request(writing_language="Schweizerdeutsch")
        prompt_ctx = pipeline._build_prompt_context(request, context)
        assert prompt_ctx.language == "de"
        assert prompt_ctx.writing_language == "Schweizerdeutsch"


def _make_pipeline() -> WritingPipeline:
    reg = MagicMock(spec=["stream", "run"])
    comp = MagicMock(spec=PromptComposer)
    comp.build = AsyncMock(
        return_value=ComposedPrompt(system="sys prompt", user="user prompt"),
    )
    asm = MagicMock(spec=WritingContextAssembler)
    asm.assemble = AsyncMock(return_value=_default_context())
    proc = MagicMock(spec=DraftProcessor)
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return WritingPipeline(
        registry=reg,
        composer=comp,
        context_assembler=asm,
        draft_processor=proc,
    )
