"""Interview-draft KB context supply tests (WS-draft-KB slice).

R3 (4d195d8e) made the WS interview draft title/genre-aware but left it
KB-blind: the ``new_chapter`` KB slots degraded to empty because the
path did not run the WS context assembler. This slice wires the
production ``WsWritingContextAssembler`` into the dispatch seam and
mirrors ``_ws_turn_support.build_prompt_context`` composition.

Assembler reuse evidence (design question, resolved empirically): the
assembler is already chapter-optional — ``ChapterRepository.get``
returns ``None`` for a missing row and ``assemble`` degrades tier-1/tier-2
to empty while novel/KB fetches still deliver (pinned by
``test_ws_context_assembler.py``); ``mode="new_chapter"`` falls through
to first-chapter-aware budget allocation (non-extend/rewrite). No slim
variant, no core change.

RULE-11 floor: an assembly or session failure degrades to ``None`` →
the KB-blind render — byte-identical to the R3 baseline (pinned here on
the real composer).

This module pins the builder and the byte-identity floor; the dispatch
production wiring (populated KB, chapter-less degrade, tier-2, session
failure) lives in ``test_interview_draft_kb_dispatch.py`` (RULE-04
split).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

from narrare.writing._interview_draft import InterviewDraftGenerator
from narrare.writing._interview_draft_support import build_prompt_context
from narrare.writing._ws_cache import InMemorySessionCache
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import LLMIntent
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing.models import WritingContext
from narrare_core.writing.session_manager import SessionManager
from tests.unit.api.writing._interview_draft_fakes import (
    identifiers,
    make_config,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

_NOVEL_TITLE = "Codex of Tides"
_TRANSCRIPT = "Author: A story about tides\n\nInterviewer: What happens?"
_KB_NAME = "Mara"
_RECENT_TITLE = "Chapter 2: The Brass Key"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _capturing_gateway() -> tuple[Mock, dict[str, str]]:
    """Gateway mock recording the ``system_prompt`` kwarg of ``stream``."""

    async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
        captured["system"] = str(kwargs["system_prompt"])
        yield StreamChunk(text="ok", is_final=True, usage=TokenUsage(1, 2, 3))

    captured: dict[str, str] = {}
    gateway = Mock()
    gateway.stream = Mock(side_effect=fake_stream)
    return gateway, captured


def _r3_baseline_context() -> PromptContext:
    """The pre-slice (R3) KB-blind PromptContext shape — byte-identity base."""
    return PromptContext(
        language="en",
        mode="new_chapter",
        author_instructions=(
            "Based on the following interview transcript, "
            "write a complete chapter draft:\n\n"
            f"{_TRANSCRIPT}"
        ),
        project_title="",
        genre="",
        extra=dict.fromkeys(
            ("chapter_outline", "kb_characters", "kb_locations", "word_target_line"),
            "",
        ),
    )


def _populated_writing_context() -> WritingContext:
    """WritingContext with every previously-empty kb slot populated."""
    return WritingContext(
        chapter_outline="Outline: the tide cave ceremony.",
        kb_characters=f"{_KB_NAME}: sentinel body",
        kb_locations="Lighthouse: sentinel location",
        kb_factions="Keepers: sentinel faction",
        kb_other="Tide engine: sentinel other",
        kb_relationships=f"{_KB_NAME} -> [ally of] -> Juno",
        kb_suggested="Suggested: sentinel entry",
        project_title=_NOVEL_TITLE,
        genre="fantasy",
        timeline_position="Day 5 of the siege.",
        recent_chapters=f"{_RECENT_TITLE} rendered",
    )


def _real_composer_generator(
    gateway: Mock,
) -> tuple[InterviewDraftGenerator, SessionManager]:
    """Generator wired with the REAL composer + pipeline (no stub masking)."""
    session_manager = SessionManager(cache=InMemorySessionCache())
    generator = InterviewDraftGenerator(
        session_manager=session_manager,
        registry=gateway,
        composer=PromptComposer(PromptRegistry()),
        config=make_config(),
        invocation_pipeline=InvocationPipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
    )
    return generator, session_manager


async def _seeded_session(
    session_manager: SessionManager,
    user_id: UUID,
    project_id: UUID,
    chapter_id: UUID,
) -> UUID:
    """Create a session with a minimal interview transcript."""
    session_id = await session_manager.create_session(chapter_id, project_id, user_id)
    await session_manager.add_message(session_id, "user", "A story about tides")
    await session_manager.add_message(session_id, "assistant", "What happens?")
    return session_id


# ---------------------------------------------------------------------------
# 1. Builder level — slot threading
# ---------------------------------------------------------------------------


class TestBuildPromptContextKbThreading:
    """build_prompt_context threads WritingContext slots into extras."""

    def test_populated_writing_context_threads_kb_slots(self) -> None:
        """Every populated kb slot + chapter fields lands in the extras."""
        ctx = build_prompt_context(_TRANSCRIPT, writing_context=_populated_writing_context())

        assert ctx.mode == "new_chapter"
        assert ctx.project_title == _NOVEL_TITLE
        assert ctx.genre == "fantasy"
        assert ctx.extra["kb_characters"] == f"{_KB_NAME}: sentinel body"
        assert ctx.extra["kb_locations"] == "Lighthouse: sentinel location"
        assert ctx.extra["kb_factions"] == "Keepers: sentinel faction"
        assert ctx.extra["kb_other"] == "Tide engine: sentinel other"
        assert ctx.extra["kb_relationships"] == f"{_KB_NAME} -> [ally of] -> Juno"
        assert ctx.extra["kb_suggested"] == "Suggested: sentinel entry"
        assert ctx.extra["chapter_outline"] == "Outline: the tide cave ceremony."
        assert ctx.extra["timeline_position"] == "Day 5 of the siege."
        assert ctx.extra["recent_chapters"] == f"{_RECENT_TITLE} rendered"
        # new_chapter route-required, label-in-value; no word target → ""
        assert ctx.extra["word_target_line"] == ""

    def test_default_writing_context_degrades_kb_blind(self) -> None:
        """No assembled context → every kb slot empty (R3 floor)."""
        ctx = build_prompt_context(_TRANSCRIPT)

        assert ctx.project_title == ""
        assert ctx.genre == ""
        for key in (
            "kb_characters",
            "kb_locations",
            "kb_factions",
            "kb_other",
            "kb_relationships",
            "kb_suggested",
            "chapter_outline",
            "timeline_position",
            "recent_chapters",
            "word_target_line",
        ):
            assert ctx.extra[key] == ""


# ---------------------------------------------------------------------------
# 2. Byte-identity — KB-empty degrade == R3 baseline (real composer)
# ---------------------------------------------------------------------------


class TestKbEmptyByteIdentity:
    """The degraded (KB-blind) render is byte-identical to the R3 render."""

    async def test_degraded_builder_render_equals_r3_baseline(self) -> None:
        """Real composer: writing_context=None renders the R3 bytes."""
        composer = PromptComposer(PromptRegistry())
        baseline = await composer.build(LLMIntent.WRITE, _r3_baseline_context())
        degraded = await composer.build(
            LLMIntent.WRITE,
            build_prompt_context(_TRANSCRIPT),
        )

        assert degraded.system == baseline.system
        assert degraded.user == baseline.user

    async def test_empty_writing_context_render_equals_r3_baseline(self) -> None:
        """Assembled-but-empty context renders the R3 bytes too."""
        composer = PromptComposer(PromptRegistry())
        baseline = await composer.build(LLMIntent.WRITE, _r3_baseline_context())
        assembled_empty = await composer.build(
            LLMIntent.WRITE,
            build_prompt_context(_TRANSCRIPT, writing_context=WritingContext()),
        )

        assert assembled_empty.system == baseline.system

    async def test_stream_draft_default_render_matches_r3_baseline(self) -> None:
        """Generator default (no writing_context) streams the R3 bytes."""
        composer = PromptComposer(PromptRegistry())
        baseline = await composer.build(LLMIntent.WRITE, _r3_baseline_context())
        gateway, captured = _capturing_gateway()
        generator, session_manager = _real_composer_generator(gateway)
        chapter_id, user_id, project_id = identifiers()
        session_id = await _seeded_session(session_manager, user_id, project_id, chapter_id)

        _ = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            )
        ]

        assert captured["system"] == baseline.system
