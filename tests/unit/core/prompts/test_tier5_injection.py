"""Tier-5 KB injection — per-route render tests (slices T1c-f).

Shared test module for the Tier-5 KB-injection spec (ADR-050 P1-D, PO ruling
1B/2B, 2026-09-10). T1c landed ``TestTier5InjectionExtend`` (extend_chapter)
here; the later slices (rewrite_selection, co_author, scene_by_scene) test in
separate per-route modules per RULE-04.

Invariant under test
--------------------
The three Tier-5 variables (``{{kb_systems}}``, ``{{kb_timelines}}``,
``{{kb_pinned}}``) are appended DIRECTLY to the existing
``{{kb_relationships}}`` template line — zero new template lines. The context
assembler (T1a, ``_helpers.optional_block``) supplies value-side labeled
blocks (``"\\n\\n<Label>:\\n<text>"``) or ``""`` for empty tiers, so:

* KB-empty novels render BYTE-IDENTICALLY to the pre-T1c prompt (golden), and
* populated tiers render their labeled blocks in fixed order after
  ``Relationships:``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline

# ---------------------------------------------------------------------------
# Golden: pre-T1c render of the EXTEND system prompt with ALL Tier-5 kb
# values empty (the KB-empty novel case). Captured 2026-09-10 — BEFORE the
# T1c template edit (prompt_version 1.3.0) — by composing the real
# PromptRegistry + PromptComposer route with the ``_extend_prompt_context``
# helper below (identical inputs). The T1c edit appends
# {{kb_systems}}{{kb_timelines}}{{kb_pinned}} to the {{kb_relationships}}
# line; with empty tiers the render MUST stay byte-identical to this
# constant (2712 bytes). Do NOT hand-edit — if the template legitimately
# changes, recapture mechanically and update this provenance note.
# ---------------------------------------------------------------------------

_GOLDEN_PRE_TIER5_EMPTY = (
    "You are a skilled creative writing assistant helping an author continue their text seamlessly"
    ". Your task is to pick up exactly where the author left off and produce prose that is indisti"
    "nguishable from the existing text — matching voice, tense, pacing, and narrative register.\n"
    "\n"
    "\n"
    "\n"
    "### Context\n"
    "\n"
    "- Project: Test Novel\n"
    "- Genre: fantasy\n"
    "- Language: English\n"
    "- Timeline: \n"
    "- **Story Structure**: \n"
    "\n"
    "### Existing Content\n"
    "\n"
    "Below is the text surrounding the continuation point. The marker `[CONTINUE FROM HERE]` shows"
    " exactly where you must resume writing. Study the style, rhythm, and voice of the pre-text ca"
    "refully.\n"
    "\n"
    "<user_provided_text>Pre-text\n"
    "[CONTINUE FROM HERE]\n"
    "Post-text</user_provided_text>\n"
    "\n"
    "### Knowledge Base\n"
    "\n"
    "\n"
    "Characters:\n"
    "\n"
    "\n"
    "Locations:\n"
    "\n"
    "\n"
    "Factions:\n"
    "\n"
    "\n"
    "Other entities:\n"
    "\n"
    "\n"
    "Relationships:\n"
    "\n"
    "\n"
    "### Suggested KB Entries\n"
    "\n"
    "Optional lower-priority generated KB suggestions. These are unaccepted candidates.\n"
    "Use them only when they support the current author instructions, project writing\n"
    "profile, current scene/timeline context, and curated KB. They must not override\n"
    "current author instructions, the project profile, current scene/timeline context,\n"
    "or curated KB.\n"
    "\n"
    "\n"
    "\n"
    "### Recent Chapters\n"
    "\n"
    "\n"
    "\n"
    "### Story Synopsis\n"
    "\n"
    "\n"
    "\n"
    "### Style Profile\n"
    "\n"
    "The author's established writing style:\n"
    "\n"
    "\n"
    "\n"
    "### Character Voice Profiles\n"
    "\n"
    "When writing dialogue, maintain each character's distinct voice based on their speech pattern"
    "s:\n"
    "\n"
    "Elena: formal, terse.\n"
    "\n"
    "**Voice consistency rules:**\n"
    "- Each character must use their established dialect, vocabulary, and verbal tics\n"
    "- Match their personality traits when they speak (formal, casual, terse, eloquent)\n"
    "- Characters should be identifiable by their speech alone, without dialogue tags\n"
    "- Do NOT make all characters sound the same — preserve their linguistic individuality\n"
    "\n"
    "### Author Voice\n"
    "\n"
    "The narrator's prose voice for this novel (descriptive profile, not raw metrics):\n"
    "\n"
    "Lyrical, close third person.\n"
    "\n"
    "### Instructions\n"
    "\n"
    "Continue the text from the `[CONTINUE FROM HERE]` marker. Follow these guidelines:\n"
    "\n"
    "1. **Seamless continuation**: The first sentence you write must flow naturally from the last "
    "sentence before the marker — no repetition, no summary, no meta-commentary\n"
    "2. **Style matching**: Replicate the author's sentence length, rhythm, diction, and narrative"
    " distance exactly\n"
    "3. **Plot continuity**: Maintain consistency with established characters, locations, and ongo"
    "ing scenes\n"
    "4. **Natural dialogue**: Use each character's established voice patterns\n"
    "5. **Pacing**: Maintain the current scene's momentum — do not artificially escalate or deflat"
    "e tension\n"
    "\n"
    "Author instructions: <user_instructions>Keep the momentum.</user_instructions>\n"
    "Word target: approximately 400 words\n"
    "Tone: Match the author's tone."
)

# Wire-format Tier-5 blocks exactly as T1a's ``_helpers.optional_block`` emits
# them (``"\n\n" + label + ":\n" + text``) — "" when the tier is empty.
_KB_SYSTEMS_BLOCK = "\n\nSystems:\nMagic costs stamina and cannot raise the dead."
_KB_TIMELINES_BLOCK = "\n\nTimelines:\nDay 1: The Fall of Thornwall."
_KB_PINNED_BLOCK = "\n\nPinned context (always included):\nNever kill Elena."


def _extend_prompt_context(
    *,
    kb_systems: str = "",
    kb_timelines: str = "",
    kb_pinned: str = "",
) -> PromptContext:
    """Build the EXTEND PromptContext the way ``stream_extend`` does.

    Mirrors ``pipeline_extend.py`` (PromptContext fields + the ``extra`` dict,
    including the Tier-5 kb keys) so the composition tests exercise the real
    route surface rather than a hand-rolled variable set.
    """
    return PromptContext(
        language="en",
        writing_language="English",
        project_title="Test Novel",
        genre="fantasy",
        tone="balanced",
        mode="extend_chapter",
        existing_content="Pre-text\n[CONTINUE FROM HERE]\nPost-text",
        author_instructions="Keep the momentum.",
        user_preferences="Concise prose.",
        avoidance_patterns="Cliches.",
        character_voice_profiles="Elena: formal, terse.",
        author_voice="Lyrical, close third person.",
        extra={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "project_id": "00000000-0000-0000-0000-000000000002",
            "chapter_outline": "Bridge scene outline.",
            "kb_characters": "",
            "kb_locations": "",
            "kb_systems": kb_systems,
            "kb_timelines": kb_timelines,
            "kb_pinned": kb_pinned,
            "recent_chapters": "",
            "character_voice_profiles": "Elena: formal, terse.",
            "word_target": "400",
            "tone_instructions": "Match the author's tone.",
            "writing_language": "English",
            "extend_length": "400",
        },
    )


_CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model", max_tokens=2000)
_USAGE = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


async def _final_only_stream() -> AsyncIterator[StreamChunk]:
    yield StreamChunk(text="", is_final=True, usage=_USAGE)


class TestTier5InjectionExtend:
    """extend_chapter (T1c): Tier-5 vars render inert when empty, labeled when populated."""

    async def test_empty_tiers_render_byte_identical_to_pre_tier5(self) -> None:
        """KB-empty render MUST equal the pre-T1c golden byte-for-byte."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.EXTEND, _extend_prompt_context())

        assert result.system == _GOLDEN_PRE_TIER5_EMPTY
        # Inert by default: no tier labels leak into the prompt.
        assert "Systems:" not in result.system
        assert "Timelines:" not in result.system
        assert "Pinned context" not in result.system
        # No unsubstituted placeholder survives composition.
        assert "{{kb_" not in result.system

    async def test_populated_tiers_render_labeled_blocks_after_relationships(self) -> None:
        """Populated tiers render their labeled blocks in order after 'Relationships:'."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(
            LLMIntent.EXTEND,
            _extend_prompt_context(
                kb_systems=_KB_SYSTEMS_BLOCK,
                kb_timelines=_KB_TIMELINES_BLOCK,
                kb_pinned=_KB_PINNED_BLOCK,
            ),
        )

        i_relationships = result.system.index("Relationships:")
        i_systems = result.system.index("\n\nSystems:\n")
        i_timelines = result.system.index("\n\nTimelines:\n")
        i_pinned = result.system.index("\n\nPinned context (always included):\n")
        assert i_relationships < i_systems < i_timelines < i_pinned

        assert "Magic costs stamina and cannot raise the dead." in result.system
        assert "Day 1: The Fall of Thornwall." in result.system
        assert "Never kill Elena." in result.system

    async def test_stream_extend_supplies_tier5_vars_in_extra(self) -> None:
        """stream_extend forwards the assembled Tier-5 blocks into ``extra``.

        Guards the pipeline wiring (pipeline_extend.py): without the three
        keys, populated tiers would silently render "" via the route's
        optional-variable fallback (RULE-11) and the KB would never reach
        the prompt.
        """
        composer = MagicMock(spec=PromptComposer)
        composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(
            return_value=WritingContext(
                project_title="Test Novel",
                genre="fantasy",
                language="en",
                tone="balanced",
                writing_language="English",
                kb_systems=_KB_SYSTEMS_BLOCK,
                kb_timelines=_KB_TIMELINES_BLOCK,
                kb_pinned=_KB_PINNED_BLOCK,
            )
        )
        registry = MagicMock(spec=["stream", "run"])
        registry.stream = MagicMock(spec=[], return_value=_final_only_stream())
        processor = MagicMock(spec=DraftProcessor)
        processor.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
        pipeline = WritingPipeline(
            registry=registry,
            composer=composer,
            context_assembler=assembler,
            draft_processor=processor,
        )
        request = GenerationRequest(
            chapter_id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            mode=GenerationMode.EXTEND,
        )

        async for _chunk in pipeline.generate(request, config=_CONFIG):
            pass

        extra: dict[str, Any] = composer.build.call_args.args[1].extra
        assert extra["kb_systems"] == _KB_SYSTEMS_BLOCK
        assert extra["kb_timelines"] == _KB_TIMELINES_BLOCK
        assert extra["kb_pinned"] == _KB_PINNED_BLOCK
