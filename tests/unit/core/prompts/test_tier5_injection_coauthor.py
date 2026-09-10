"""Tier-5 KB injection — co_author render tests (slice T1e).

Companion module to ``test_tier5_injection.py`` (T1c, extend_chapter) and
``test_tier5_injection_rewrite.py`` (T1d, rewrite_selection): the shared
module already sits at 301 lines, so appending the T1e class would exceed
the 400-line RULE-04 cap — the co_author route gets its own module with the
same shape and its own golden (per the T1e slice brief).

Invariant under test
--------------------
Mirrors T1c/T1d for the CO_AUTHOR route: the three Tier-5 variables
(``{{kb_systems}}``, ``{{kb_timelines}}``, ``{{kb_pinned}}``) are appended
DIRECTLY to the existing ``{{kb_relationships}}`` template line — zero new
template lines. The context assembler (T1a, ``_helpers.optional_block``)
supplies value-side labeled blocks (``"\\n\\n<Label>:\\n<text>"``) or ``""``
for empty tiers, so:

* KB-empty novels render BYTE-IDENTICALLY to the pre-T1e prompt (golden), and
* populated tiers render their labeled blocks in fixed order after
  ``Relationships:``.
"""

from __future__ import annotations

from dataclasses import replace
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
from narrare_core.writing._helpers import kb_context_extras
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline
from narrare_core.writing.pipeline_coauthor import get_co_author_focus_instructions
from narrare_core.writing.style_variants import get_style_variant_instructions

# ---------------------------------------------------------------------------
# Golden: pre-T1e render of the CO_AUTHOR system prompt with ALL Tier-5 kb
# values empty (the KB-empty novel case). Captured 2026-09-10 — BEFORE the
# T1e template edit (prompt_version 1.4.0) — by composing the real
# PromptRegistry + PromptComposer route with the ``_coauthor_prompt_context``
# helper below (identical inputs). The T1e edit appends
# {{kb_systems}}{{kb_timelines}}{{kb_pinned}} to the {{kb_relationships}}
# line; with empty tiers the render MUST stay byte-identical to this
# constant (3331 bytes). Do NOT hand-edit — if the template legitimately
# changes, recapture mechanically and update this provenance note.
# ---------------------------------------------------------------------------

_GOLDEN_PRE_TIER5_EMPTY_COAUTHOR = (
    "You are a precise text improvement specialist. Your role is to suggest specific,\ntargeted imp"
    "rovements to the author's text while preserving their voice and style.\n\n\n\n### Context\n\n-"
    " Project: Test Novel\n- Genre: fantasy\n- Language: English\n- Timeline: \n- **Story Structure"
    "**: \n\n### Knowledge Base\n\n\nCharacters:\n\n\nLocations:\n\n\nFactions:\n\n\nOther entities"
    ":\n\n\nRelationships:\n\n\n### Suggested KB Entries\n\nOptional lower-priority generated KB su"
    "ggestions. These are unaccepted candidates.\nUse them only when they support the current autho"
    "r instructions, project writing\nprofile, current scene/timeline context, and curated KB. They"
    " must not override\ncurrent author instructions, the project profile, current scene/timeline c"
    "ontext,\nor curated KB.\n\n\n\n### Character Voice Profiles\n\nWhen rewriting dialogue or narr"
    "ation in a character's voice, maintain their distinct speech patterns:\n\nElena: formal, terse"
    ".\n\n**Voice consistency rules:**\n- Each character must use their established dialect, vocabu"
    "lary, and verbal tics\n- Match their personality traits when they speak (formal, casual, terse"
    ", eloquent)\n- Characters should be identifiable by their speech alone, without dialogue tags"
    "\n\n### Author Voice\n\nThe narrator's prose voice for this novel (descriptive profile, not ra"
    "w metrics):\n\nLyrical, close third person.\n\n### Recent Chapters\n\n\n\n### Style Profile\n"
    "\nThe author's established writing style:\n\n\n\n### Text to Improve\n\nThe following is the p"
    "assage the author wants you to improve:\n\n<user_provided_text>They crossed at dusk.</user_pro"
    "vided_text><user_provided_text>The old bridge groaned under their weight.</user_provided_text>"
    "<user_provided_text>Nobody spoke again.</user_provided_text>\n\n### Focus Areas\n\nFocus ONLY "
    "on these improvement types (the author selected these):\n\n### word_choice\nLook for weak verb"
    "s, imprecise nouns, and redundancies. Replace them with stronger, more specific alternatives. "
    "Keep the sentence structure intact — only change individual words and phrases.\n\nDo NOT sugge"
    "st changes outside these focus areas.\n\n### Style Variant Direction\n\n\n\n### Guidelines\n\n"
    "- Improve the text while keeping the author's voice and style intact\n- Make specific, targete"
    "d changes — not wholesale rewrites\n- Preserve the narrative perspective, character voice, and"
    " scene structure\n- When improving dialogue, make it sound natural for the character\n- When i"
    "mproving description, use sensory details that fit the established style\n- When improving wor"
    "d choice, select stronger, more precise alternatives\n\n### Output Format\n\nProvide the COMPL"
    "ETE revised version of the text. Keep the structure and flow\nof the original while making foc"
    "used improvements in the selected areas.\n\nDo NOT use XML tags, alternative markers, or any s"
    "tructural formatting — just\nthe revised text. Your ONLY output is the improved version of the"
    " original\npassage.\n\n### Do NOT\n\n- Do NOT change the narrative perspective\n- Do NOT add o"
    "r remove characters from the scene\n- Do NOT introduce new plot elements\n- Do NOT over-explai"
    "n or add unnecessary exposition\n- Do NOT flatten the author's voice into generic prose\n- Do "
    "NOT suggest improvements outside the selected focus areas\n\n### User Preferences\n\nConcise p"
    "rose.\n\n### Constraints\n\n- Write in English\n- Match the rhythm and register of the surroun"
    "ding context\n- Respect the author's avoidance patterns: Cliches."
)

# Wire-format Tier-5 blocks exactly as T1a's ``_helpers.optional_block`` emits
# them (``"\n\n" + label + ":\n" + text``) — "" when the tier is empty.
_KB_SYSTEMS_BLOCK = "\n\nSystems:\nMagic costs stamina and cannot raise the dead."
_KB_TIMELINES_BLOCK = "\n\nTimelines:\nDay 1: The Fall of Thornwall."
_KB_PINNED_BLOCK = "\n\nPinned context (always included):\nNever kill Elena."

# A3 populated-delta sentinels: raw (render-ready) values for the five KB
# variables the co_author route previously assembled but never supplied.
_KB_RELATIONSHIPS_TEXT = "Elena and Mara: uneasy allies since the siege"
_KB_FACTIONS_TEXT = "### Faction: Bridge Wardens"
_KB_OTHER_TEXT = "### Item: Rusty Key"
_KB_SUGGESTED_TEXT = "### Character: Bernd (unaccepted candidate)"
_KB_CONTEXT_WARNINGS_TEXT = "Orphan reference: char-9 (removed entity)"


def _coauthor_prompt_context(
    *,
    kb_systems: str = "",
    kb_timelines: str = "",
    kb_pinned: str = "",
) -> PromptContext:
    """Build the CO_AUTHOR PromptContext the way ``stream_coauthor`` does.

    Mirrors ``pipeline_coauthor.py`` (PromptContext fields + the ``extra``
    dict, including the Tier-5 kb keys) so the composition tests exercise the
    real route surface rather than a hand-rolled variable set. The injected
    instructions come from the real pipeline helpers
    (``get_co_author_focus_instructions`` / ``get_style_variant_instructions``)
    to prevent drift; ``tone_instructions`` is "" because the bundled
    ``balanced`` tone maps to an empty string (``TONE_INSTRUCTIONS``).
    """
    return PromptContext(
        language="en",
        writing_language="English",
        project_title="Test Novel",
        genre="fantasy",
        tone="balanced",
        mode="co_author",
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
            "co_author_focus_instructions": get_co_author_focus_instructions(["word_choice"]),
            "style_variant_instructions": get_style_variant_instructions(None),
        },
    )


_CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model", max_tokens=2000)
_USAGE = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


async def _final_only_stream() -> AsyncIterator[StreamChunk]:
    yield StreamChunk(text="", is_final=True, usage=_USAGE)


class TestTier5InjectionCoAuthor:
    """co_author (T1e): Tier-5 vars render inert when empty, labeled when populated."""

    async def test_empty_tiers_render_byte_identical_to_pre_tier5(self) -> None:
        """KB-empty render MUST equal the pre-T1e golden byte-for-byte."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.CO_AUTHOR, _coauthor_prompt_context())

        assert result.system == _GOLDEN_PRE_TIER5_EMPTY_COAUTHOR
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
            LLMIntent.CO_AUTHOR,
            _coauthor_prompt_context(
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

    async def test_stream_coauthor_supplies_tier5_vars_in_extra(self) -> None:
        """stream_coauthor forwards the assembled Tier-5 blocks into ``extra``.

        Guards the pipeline wiring (pipeline_coauthor.py): without the three
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
            mode=GenerationMode.CO_AUTHOR,
        )

        async for _chunk in pipeline.generate(
            request,
            config=_CONFIG,
            selection_text="The old bridge groaned under their weight.",
            co_author_focus=["word_choice"],
        ):
            pass

        extra: dict[str, Any] = composer.build.call_args.args[1].extra
        assert extra["kb_systems"] == _KB_SYSTEMS_BLOCK
        assert extra["kb_timelines"] == _KB_TIMELINES_BLOCK
        assert extra["kb_pinned"] == _KB_PINNED_BLOCK

    async def test_populated_kb_vars_render_once_at_placeholders(self) -> None:
        """A3 delta: the five previously-unsupplied KB vars render exactly once.

        ``extra`` is built the way the route now does: base extras merged with
        ``kb_context_extras(WritingContext)``.
        """
        context = WritingContext(
            kb_relationships=_KB_RELATIONSHIPS_TEXT,
            kb_factions=_KB_FACTIONS_TEXT,
            kb_other=_KB_OTHER_TEXT,
            kb_suggested=_KB_SUGGESTED_TEXT,
            kb_context_warnings=_KB_CONTEXT_WARNINGS_TEXT,
        )
        base = _coauthor_prompt_context()
        prompt_ctx = replace(base, extra={**base.extra, **kb_context_extras(context)})
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.CO_AUTHOR, prompt_ctx)

        assert result.system.count(_KB_RELATIONSHIPS_TEXT) == 1
        assert result.system.count(_KB_FACTIONS_TEXT) == 1
        assert result.system.count(_KB_OTHER_TEXT) == 1
        assert result.system.count(_KB_SUGGESTED_TEXT) == 1
        assert result.system.count(_KB_CONTEXT_WARNINGS_TEXT) == 1
        # Each value lands directly at its static template label.
        assert f"Knowledge Base\n\n{_KB_CONTEXT_WARNINGS_TEXT}\nCharacters:" in result.system
        assert f"Factions:\n{_KB_FACTIONS_TEXT}\n" in result.system
        assert f"Other entities:\n{_KB_OTHER_TEXT}\n" in result.system
        assert f"Relationships:\n{_KB_RELATIONSHIPS_TEXT}\n" in result.system
        assert f"curated KB.\n\n{_KB_SUGGESTED_TEXT}\n" in result.system
        assert "Locations:" in result.system  # remaining static label unchanged
        assert "{{kb_" not in result.system

        # Mutation-style: helper output all "" (KB-empty novel) → the render
        # equals the Tier-5 golden byte-for-byte (supplied-empty is neutral).
        empty_ctx = replace(base, extra={**base.extra, **kb_context_extras(WritingContext())})
        empty_result = await composer.build(LLMIntent.CO_AUTHOR, empty_ctx)
        assert empty_result.system == _GOLDEN_PRE_TIER5_EMPTY_COAUTHOR

    async def test_stream_coauthor_supplies_all_kb_vars_in_extra(self) -> None:
        """A3 wiring: the kb_context_extras merge forwards all ten KB vars.

        Without the merge in pipeline_coauthor.py, the five previously-unsupplied
        variables would silently render "" via the optional-variable fallback
        (RULE-11) and assembled KB content would never reach the prompt.
        """
        composer = MagicMock(spec=PromptComposer)
        composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(
            return_value=WritingContext(
                kb_relationships=_KB_RELATIONSHIPS_TEXT,
                kb_factions=_KB_FACTIONS_TEXT,
                kb_other=_KB_OTHER_TEXT,
                kb_suggested=_KB_SUGGESTED_TEXT,
                kb_context_warnings=_KB_CONTEXT_WARNINGS_TEXT,
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
            mode=GenerationMode.CO_AUTHOR,
        )

        async for _chunk in pipeline.generate(
            request,
            config=_CONFIG,
            selection_text="The old bridge groaned under their weight.",
            co_author_focus=["word_choice"],
        ):
            pass

        extra: dict[str, Any] = composer.build.call_args.args[1].extra
        assert extra["kb_relationships"] == _KB_RELATIONSHIPS_TEXT
        assert extra["kb_factions"] == _KB_FACTIONS_TEXT
        assert extra["kb_other"] == _KB_OTHER_TEXT
        assert extra["kb_suggested"] == _KB_SUGGESTED_TEXT
        assert extra["kb_context_warnings"] == _KB_CONTEXT_WARNINGS_TEXT
        # Previously-supplied variables keep identical values ("" here).
        assert extra["kb_characters"] == ""
        assert extra["kb_locations"] == ""
