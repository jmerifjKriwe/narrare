"""Tier-5 KB injection — rewrite_selection render tests (slice T1d).

Companion module to ``test_tier5_injection.py`` (T1c, extend_chapter): the
shared module already sits at 301 lines, so appending the T1d class would
exceed the 400-line RULE-04 cap — the rewrite_selection route gets its own
module with the same shape and its own golden (per the T1d slice brief).

Invariant under test
--------------------
Mirrors T1c for the REWRITE route: the three Tier-5 variables
(``{{kb_systems}}``, ``{{kb_timelines}}``, ``{{kb_pinned}}``) are appended
DIRECTLY to the existing ``{{kb_relationships}}`` template line — zero new
template lines. The context assembler (T1a, ``_helpers.optional_block``)
supplies value-side labeled blocks (``"\\n\\n<Label>:\\n<text>"``) or ``""``
for empty tiers, so:

* KB-empty novels render BYTE-IDENTICALLY to the pre-T1d prompt (golden), and
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
from narrare_core.writing.pipeline_rewrite import get_rewrite_mode_instructions
from narrare_core.writing.style_variants import get_style_variant_instructions

# ---------------------------------------------------------------------------
# Golden: pre-T1d render of the REWRITE system prompt with ALL Tier-5 kb
# values empty (the KB-empty novel case). Captured 2026-09-10 — BEFORE the
# T1d template edit (prompt_version 2.3.0) — by composing the real
# PromptRegistry + PromptComposer route with the ``_rewrite_prompt_context``
# helper below (identical inputs). The T1d edit appends
# {{kb_systems}}{{kb_timelines}}{{kb_pinned}} to the {{kb_relationships}}
# line; with empty tiers the render MUST stay byte-identical to this
# constant (3680 bytes). Do NOT hand-edit — if the template
# legitimately changes, recapture mechanically and update this provenance
# note.
# ---------------------------------------------------------------------------

_GOLDEN_PRE_TIER5_EMPTY_REWRITE = (
    "You are a precise text revision specialist. Your role is to rewrite specific portions of tex"
    "t based on the author's direction while preserving their established voice, style, and narra"
    "tive consistency.\n\n\n\n### Context\n\n- Project: Test Novel\n- Genre: fantasy\n- Language:"
    " English\n- Timeline: \n- **Story Structure**: \n\n### Knowledge Base\n\n\nCharacters:\n\n\n"
    "Locations:\n\n\nFactions:\n\n\nOther entities:\n\n\nRelationships:\n\n\n### Suggested KB Ent"
    "ries\n\nOptional lower-priority generated KB suggestions. These are unaccepted candidates.\n"
    "Use them only when they support the current author instructions, project writing\nprofile, c"
    "urrent scene/timeline context, and curated KB. They must not override\ncurrent author instru"
    "ctions, the project profile, current scene/timeline context,\nor curated KB.\n\n\n\n### Rece"
    "nt Chapters\n\n\n\n### Style Profile\n\nThe author's established writing style:\n\n\n\n### C"
    "haracter Voice Profiles\n\nWhen rewriting dialogue or narration in a character's voice, main"
    "tain their distinct speech patterns:\n\nElena: formal, terse.\n\n**Voice consistency rules:*"
    "*\n- Each character must use their established dialect, vocabulary, and verbal tics\n- Match"
    " their personality traits when they speak (formal, casual, terse, eloquent)\n- Characters sh"
    "ould be identifiable by their speech alone, without dialogue tags\n\n### Author Voice\n\nThe"
    " narrator's prose voice for this novel (descriptive profile, not raw metrics):\n\nLyrical, c"
    "lose third person.\n\n### Text to Rewrite\n\nThe following is the text selection the author "
    "wants rewritten. It is surrounded by its immediate context (before and after) so you can mat"
    "ch the surrounding rhythm and register.\n\n**Text before selection:**\n<user_provided_text>T"
    "hey crossed at dusk.</user_provided_text>\n\n**Selection to rewrite:**\n<user_provided_text>"
    "The old bridge groaned under their weight.</user_provided_text>\n\n**Text after selection:**"
    "\n<user_provided_text>Nobody spoke again.</user_provided_text>\n\n### Rewrite Instructions\n"
    "\nAdjust the emotional language, pacing, and word choice to match the requested tone shift. "
    "Modify connotations, sensory details, and emotional register while preserving the underlying"
    " meaning and narrative structure.\n\nAuthor instructions: <user_instructions>Keep the moment"
    "um.</user_instructions>\nTone: \n\n### Style Variant Direction\n\n\n\n### Output Format\n\nY"
    "ou MUST produce exactly 1 alternative(s). Wrap each alternative in `<alternative>` tags with"
    ' a descriptive label:\n\n```\n<alternative label="Descriptive label for this version">\n[R'
    "ewritten text here]\n</alternative>\n```\n\n**CRITICAL TAG RULES:**\n- You MUST NOT use `<al"
    "ternative>` or `</alternative>` tags anywhere inside the rewritten text content\n- These tag"
    "s are ONLY used as structural delimiters between alternatives\n- If you need to represent an"
    'gle brackets in the prose, use them only as part of narrative (e.g., "he whispered <no>" i'
    "s fine — but never `<alternative>` or `</alternative>`)\n\nUse a `<scratchpad>` to analyze t"
    "he original text and plan your revision strategy before writing. Then output the alternative"
    "(s) — no commentary or explanation needed unless the author asked for it.\n\n### Do NOT\n\n-"
    " Do NOT change the narrative perspective unless explicitly asked\n- Do NOT add or remove cha"
    "racters from the scene\n- Do NOT flatten the author's voice into generic prose\n- Do NOT int"
    "roduce new plot elements in the rewritten section\n- Do NOT over-explain or add exposition t"
    "hat wasn't in the original\n- Do NOT use `<alternative>` or `</alternative>` tags within the"
    " prose content itself\n\n### User Preferences\n\nConcise prose.\n\n### Constraints\n\n- Writ"
    "e in English\n- Match the rhythm and register of the surrounding context\n- Respect the auth"
    "or's avoidance patterns: Cliches."
)

# Wire-format Tier-5 blocks exactly as T1a's ``_helpers.optional_block`` emits
# them (``"\n\n" + label + ":\n" + text``) — "" when the tier is empty.
_KB_SYSTEMS_BLOCK = "\n\nSystems:\nMagic costs stamina and cannot raise the dead."
_KB_TIMELINES_BLOCK = "\n\nTimelines:\nDay 1: The Fall of Thornwall."
_KB_PINNED_BLOCK = "\n\nPinned context (always included):\nNever kill Elena."


def _rewrite_prompt_context(
    *,
    kb_systems: str = "",
    kb_timelines: str = "",
    kb_pinned: str = "",
) -> PromptContext:
    """Build the REWRITE PromptContext the way ``stream_rewrite`` does.

    Mirrors ``pipeline_rewrite.py`` (PromptContext fields + the ``extra``
    dict, including the Tier-5 kb keys) so the composition tests exercise
    the real route surface rather than a hand-rolled variable set. The
    injected instructions come from the real pipeline helpers
    (``get_rewrite_mode_instructions`` / ``get_style_variant_instructions``)
    to prevent drift; ``tone_instructions`` is "" because the bundled
    ``balanced`` tone maps to an empty string (``TONE_INSTRUCTIONS``).
    """
    return PromptContext(
        language="en",
        writing_language="English",
        project_title="Test Novel",
        genre="fantasy",
        tone="balanced",
        mode="rewrite_selection",
        existing_content="The old bridge groaned under their weight.",
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
            "tone_instructions": "",
            "writing_language": "English",
            "selection_text": "The old bridge groaned under their weight.",
            "context_before": "They crossed at dusk.",
            "context_after": "Nobody spoke again.",
            "rewrite_mode_instructions": get_rewrite_mode_instructions("tone"),
            "style_variant_instructions": get_style_variant_instructions(None),
            "count": "1",
        },
    )


_CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model", max_tokens=2000)
_USAGE = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


async def _final_only_stream() -> AsyncIterator[StreamChunk]:
    yield StreamChunk(text="", is_final=True, usage=_USAGE)


class TestTier5InjectionRewrite:
    """rewrite_selection (T1d): Tier-5 vars render inert when empty, labeled when populated."""

    async def test_empty_tiers_render_byte_identical_to_pre_tier5(self) -> None:
        """KB-empty render MUST equal the pre-T1d golden byte-for-byte."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.REWRITE, _rewrite_prompt_context())

        assert result.system == _GOLDEN_PRE_TIER5_EMPTY_REWRITE
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
            LLMIntent.REWRITE,
            _rewrite_prompt_context(
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

    async def test_stream_rewrite_supplies_tier5_vars_in_extra(self) -> None:
        """stream_rewrite forwards the assembled Tier-5 blocks into ``extra``.

        Guards the pipeline wiring (pipeline_rewrite.py): without the three
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
            mode=GenerationMode.REWRITE,
        )

        async for _chunk in pipeline.generate(request, config=_CONFIG):
            pass

        extra: dict[str, Any] = composer.build.call_args.args[1].extra
        assert extra["kb_systems"] == _KB_SYSTEMS_BLOCK
        assert extra["kb_timelines"] == _KB_TIMELINES_BLOCK
        assert extra["kb_pinned"] == _KB_PINNED_BLOCK
