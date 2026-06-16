"""Tests für WritingGraph review_draft step with WritingContext enrichment.

Verifies that the review step assembles KB context, enriches the prompt,
and gracefully degrades when context assembly fails.

Node-Tests via StepContext + graph.nodes[...].call() with mocked agents.
No real LLM calls (RULE-01).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_graph import StepContext

if TYPE_CHECKING:
    from narrare_core.agents.review_agent import ReviewDeps

from narrare_core.agents.review_types import ReviewOutput
from narrare_core.agents.writing_graph_prompts import (
    _assemble_review_context,
    _enrich_prompt_context_with_kb,
    get_review_prompt,
)
from narrare_core.agents.writing_graph_types import (
    Approved,
    WritingDeps,
    WritingState,
    create_writing_graph,
)
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.prompts.context import PromptContext
from narrare_core.writing.models import WritingContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CH_ID = "550e8400-e29b-41d4-a716-446655440000"
_NOVEL_ID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"


def _make_deps(**overrides: Any) -> WritingDeps:
    defaults: dict[str, Any] = {
        "registry": AsyncMock(),
        "composer": AsyncMock(),
        "genre": "fantasy",
        "tone": "balanced",
        "word_target": 1000,
    }
    defaults.update(overrides)
    return WritingDeps(**defaults)


def _make_state(**overrides: Any) -> WritingState:
    defaults: dict[str, Any] = {"chapter_id": "ch-01"}
    defaults.update(overrides)
    return WritingState(**defaults)


def _make_writing_context(**overrides: Any) -> WritingContext:
    defaults: dict[str, Any] = {
        "kb_characters": "Elena — warrior queen",
        "kb_locations": "Dark Forest",
        "kb_factions": "Rebels",
        "kb_suggested": "Shadow Council",
        "recent_chapters": "Chapter 1: The hero arrived.",
        "user_preferences": "Avoid excessive adjectives.",
    }
    defaults.update(overrides)
    return WritingContext(**defaults)


@pytest.fixture()
def writing_graph():  # type: ignore[no-untyped-def]
    return create_writing_graph()


async def _call_review_node(
    writing_graph: Any,
    state: WritingState,
    deps: WritingDeps,
    mock_output: ReviewOutput,
) -> tuple[Any, ReviewDeps | None]:
    """Call review_draft node, return (result, captured_deps)."""
    node = writing_graph.nodes["review_draft"]
    captured_deps: ReviewDeps | None = None

    with (
        patch(
            "narrare_core.agents.writing_graph.get_model",
            new_callable=AsyncMock,
            return_value="mock_model",
        ),
        patch("narrare_core.agents.writing_graph.ReviewAgent") as MockAgent,
    ):
        mock_instance = AsyncMock()
        original_run = AsyncMock(return_value=mock_output)

        async def capture_run(prompt: str, deps: ReviewDeps, **kw: Any) -> ReviewOutput:
            nonlocal captured_deps
            captured_deps = deps
            return await original_run(prompt, deps, **kw)

        mock_instance.run = capture_run
        MockAgent.return_value = mock_instance

        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)

    return result, captured_deps


# ---------------------------------------------------------------------------
# A. _assemble_review_context — Context Assembly
# ---------------------------------------------------------------------------


class TestAssembleReviewContext:
    """_assemble_review_context assembles context or gracefully returns None."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_assembler(self) -> None:
        deps = _make_deps(context_assembler=None)
        state = _make_state(chapter_id="ch-01", novel_id="novel-01")
        assert await _assemble_review_context(deps, state) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_chapter_id(self) -> None:
        assembler = AsyncMock()
        deps = _make_deps(context_assembler=assembler)
        state = _make_state(chapter_id="", novel_id="novel-01")
        assert await _assemble_review_context(deps, state) is None
        assembler.assemble.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_novel_id(self) -> None:
        assembler = AsyncMock()
        deps = _make_deps(context_assembler=assembler)
        state = _make_state(chapter_id="ch-01", novel_id="")
        assert await _assemble_review_context(deps, state) is None
        assembler.assemble.assert_not_called()

    @pytest.mark.asyncio
    async def test_assembles_context_when_available(self) -> None:
        expected = _make_writing_context()
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(return_value=expected)
        deps = _make_deps(context_assembler=assembler)
        state = _make_state(chapter_id=_CH_ID, novel_id=_NOVEL_ID)
        result = await _assemble_review_context(deps, state)
        assert result is expected
        assembler.assemble.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_failure(self) -> None:
        """context_assembler raises → returns None (RULE-11: logged, not silent)."""
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(side_effect=RuntimeError("DB lost"))
        deps = _make_deps(context_assembler=assembler)
        state = _make_state(chapter_id=_CH_ID, novel_id=_NOVEL_ID)
        assert await _assemble_review_context(deps, state) is None


# ---------------------------------------------------------------------------
# B. Prompt Enrichment — PromptComposer Path
# ---------------------------------------------------------------------------


class TestEnrichPromptContextWithKB:
    """PromptContext.extra gets populated with KB data."""

    def test_populates_extra_with_kb_data(self) -> None:
        ctx = _make_writing_context()
        prompt_ctx = PromptContext(language="en", genre="fantasy", tone="balanced")
        prompt_ctx.extra = {"word_target": "1000"}
        _enrich_prompt_context_with_kb(prompt_ctx, ctx)
        assert prompt_ctx.extra["kb_characters"] == "Elena — warrior queen"
        assert prompt_ctx.extra["kb_locations"] == "Dark Forest"
        assert prompt_ctx.extra["kb_factions"] == "Rebels"
        assert prompt_ctx.extra["kb_suggested"] == "Shadow Council"
        assert prompt_ctx.extra["recent_chapters"] == "Chapter 1: The hero arrived."
        assert prompt_ctx.extra["user_preferences"] == "Avoid excessive adjectives."
        assert prompt_ctx.extra["word_target"] == "1000"

    def test_skips_empty_fields(self) -> None:
        prompt_ctx = PromptContext(language="en", genre="fantasy", tone="balanced")
        prompt_ctx.extra = {}
        _enrich_prompt_context_with_kb(prompt_ctx, WritingContext(kb_characters="Elena"))
        assert prompt_ctx.extra["kb_characters"] == "Elena"
        assert "kb_locations" not in prompt_ctx.extra


# ---------------------------------------------------------------------------
# D. get_review_prompt — Integration
# ---------------------------------------------------------------------------


class TestGetReviewPromptWithContext:
    """get_review_prompt assembles context and returns it."""

    @pytest.mark.asyncio
    async def test_returns_writing_context_in_tuple(self) -> None:
        """With no assembler, writing_ctx is None and composed prompt returned."""
        mock_composer = AsyncMock()
        mock_composer.build = AsyncMock(return_value=ComposedPrompt(system="SYS", user="USER"))
        deps = _make_deps(context_assembler=None, composer=mock_composer)
        state = _make_state(draft="A brave hero sets out.")
        sys_prompt, user_prompt, writing_ctx = await get_review_prompt(
            composer=mock_composer,
            deps=deps,
            state=state,
            word_count=5,
        )
        assert sys_prompt == "SYS"
        assert user_prompt == "USER"
        assert writing_ctx is None

    @pytest.mark.asyncio
    async def test_composer_path_enriches_context_with_kb(self) -> None:
        """PromptComposer path enriches PromptContext.extra with KB data."""
        writing_ctx = _make_writing_context()
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(return_value=writing_ctx)
        mock_composer = AsyncMock()
        mock_composer.build = AsyncMock(return_value=ComposedPrompt(system="SYS", user="USER"))
        deps = _make_deps(context_assembler=assembler, word_target=1000, composer=mock_composer)
        state = _make_state(draft="The hero fights.", chapter_id=_CH_ID, novel_id=_NOVEL_ID)

        _, _, returned_ctx = await get_review_prompt(
            composer=mock_composer,
            deps=deps,
            state=state,
            word_count=3,
        )
        assert returned_ctx is writing_ctx
        # Verify PromptContext.extra was enriched with KB data
        called_ctx = mock_composer.build.call_args.args[1]
        assert called_ctx.extra["kb_characters"] == "Elena — warrior queen"
        assert called_ctx.extra["kb_locations"] == "Dark Forest"
        assert called_ctx.extra["recent_chapters"] == "Chapter 1: The hero arrived."


# ---------------------------------------------------------------------------
# E. review_draft step — Full Integration via Graph Node
# ---------------------------------------------------------------------------


class TestReviewDraftWithContext:
    """review_draft step assembles context and passes it to ReviewDeps."""

    @pytest.mark.asyncio
    async def test_review_with_context_assembler(self, writing_graph: Any) -> None:
        """review_draft uses context_assembler when available."""
        writing_ctx = _make_writing_context()
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(return_value=writing_ctx)

        state = _make_state(
            draft=" ".join(["word"] * 800),
            attempts=0,
            chapter_id=_CH_ID,
            novel_id=_NOVEL_ID,
        )
        deps = _make_deps(word_target=1000, context_assembler=assembler)

        result, captured = await _call_review_node(
            writing_graph,
            state,
            deps,
            ReviewOutput(approved=True, feedback="Consistent.", quality_score=8),
        )
        assert isinstance(result, Approved)
        assert captured is not None
        assert captured.writing_context is writing_ctx
        assert captured.word_target == 1000

    @pytest.mark.asyncio
    async def test_review_without_assembler(self, writing_graph: Any) -> None:
        """review_draft works without context_assembler — backward compat."""
        state = _make_state(draft=" ".join(["word"] * 800), attempts=0)
        deps = _make_deps(word_target=1000, context_assembler=None)

        result, captured = await _call_review_node(
            writing_graph,
            state,
            deps,
            ReviewOutput(approved=True, feedback="Good.", quality_score=7),
        )
        assert isinstance(result, Approved)
        assert captured is not None
        assert captured.writing_context is None

    @pytest.mark.asyncio
    async def test_review_context_assembly_failure_graceful(
        self,
        writing_graph: Any,
    ) -> None:
        """context_assembler raises → review proceeds without context."""
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(side_effect=RuntimeError("Service down"))

        state = _make_state(
            draft=" ".join(["word"] * 800),
            attempts=0,
            chapter_id=_CH_ID,
            novel_id=_NOVEL_ID,
        )
        deps = _make_deps(word_target=1000, context_assembler=assembler)

        result, captured = await _call_review_node(
            writing_graph,
            state,
            deps,
            ReviewOutput(approved=True, feedback="No KB context.", quality_score=6),
        )
        assert isinstance(result, Approved)
        assert captured is not None
        assert captured.writing_context is None  # gracefully degraded
