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

* KB-empty novels render BYTE-IDENTICALLY to the R2-C1 baseline golden, and
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

# ---------------------------------------------------------------------------
# Golden: EXTEND system prompt with ALL Tier-5 kb values empty (the
# KB-empty novel case).
#
# Provenance: originally captured 2026-09-10 — BEFORE the T1c template edit
# (prompt_version 1.3.0) — by composing the real PromptRegistry +
# PromptComposer route with the ``_extend_prompt_context`` helper below
# (identical inputs). The T1c edit appends
# {{kb_systems}}{{kb_timelines}}{{kb_pinned}} to the {{kb_relationships}}
# line; with empty tiers the render stayed byte-identical (2720 bytes —
# truncated at the then-rogue ``## Output Format`` header).
#
# RE-CAPTURED 2026-09-11 for R2-C1 header demotion (prompt_version 1.5.0):
# the rogue ``## Output Format`` / ``## Do NOT`` headers were demoted to
# ``###`` (only ``## System Prompt`` remains level-2), so the previously
# dropped Output Format / User Preferences / Do NOT / Constraints sections
# now render in the system prompt. Recaptured mechanically with the real
# PromptRegistry + PromptComposer via ``_extend_prompt_context()``
# (identical inputs): 3731 UTF-8 bytes (3721 chars). Empty-tier
# byte-identity is asserted relative to THIS baseline. Do NOT hand-edit —
# if the template legitimately changes, recapture mechanically and update
# this provenance note.
# ---------------------------------------------------------------------------

_GOLDEN_EMPTY_TIERS_BASELINE = (
    "You are a skilled creative writing assistant helping an author continue their text seaml"
    "essly. Your task is to pick up exactly where the author left off and produce prose that "
    "is indistinguishable from the existing text — matching voice, tense, pacing, and na"
    "rrative register.\n\n\n\n### Context\n\n- Project: Test Novel\n- Genre: fantasy\n- Langu"
    "age: English\n- Timeline: \n- **Story Structure**: \n\n### Existing Content\n\nBelow is "
    "the text surrounding the continuation point. The marker `[CONTINUE FROM HERE]` shows exa"
    "ctly where you must resume writing. Study the style, rhythm, and voice of the pre-text c"
    "arefully.\n\n<user_provided_text>Pre-text\n[CONTINUE FROM HERE]\nPost-text</user_provide"
    "d_text>\n\n### Knowledge Base\n\n\nCharacters:\n\n\nLocations:\n\n\nFactions:\n\n\nOther"
    " entities:\n\n\nRelationships:\n\n\n### Suggested KB Entries\n\nOptional lower-priority "
    "generated KB suggestions. These are unaccepted candidates.\nUse them only when they supp"
    "ort the current author instructions, project writing\nprofile, current scene/timeline co"
    "ntext, and curated KB. They must not override\ncurrent author instructions, the project "
    "profile, current scene/timeline context,\nor curated KB.\n\n\n\n### Recent Chapters\n\n"
    "\n\n### Story Synopsis\n\n\n\n### Style Profile\n\nThe author's established writing styl"
    "e:\n\n\n\n### Character Voice Profiles\n\nWhen writing dialogue, maintain each character"
    "'s distinct voice based on their speech patterns:\n\nElena: formal, terse.\n\n**Voice co"
    "nsistency rules:**\n- Each character must use their established dialect, vocabulary, and"
    " verbal tics\n- Match their personality traits when they speak (formal, casual, terse, e"
    "loquent)\n- Characters should be identifiable by their speech alone, without dialogue ta"
    "gs\n- Do NOT make all characters sound the same — preserve their linguistic individ"
    "uality\n\n### Author Voice\n\nThe narrator's prose voice for this novel (descriptive pro"
    "file, not raw metrics):\n\nLyrical, close third person.\n\n### Instructions\n\nContinue "
    "the text from the `[CONTINUE FROM HERE]` marker. Follow these guidelines:\n\n1. **Seamle"
    "ss continuation**: The first sentence you write must flow naturally from the last senten"
    "ce before the marker — no repetition, no summary, no meta-commentary\n2. **Style ma"
    "tching**: Replicate the author's sentence length, rhythm, diction, and narrative distanc"
    "e exactly\n3. **Plot continuity**: Maintain consistency with established characters, loc"
    "ations, and ongoing scenes\n4. **Natural dialogue**: Use each character's established vo"
    "ice patterns\n5. **Pacing**: Maintain the current scene's momentum — do not artific"
    "ially escalate or deflate tension\n\nAuthor instructions: <user_instructions>Keep the mo"
    "mentum.</user_instructions>\nWord target: approximately 400 words\nTone: Match the autho"
    "r's tone.\n\n### Output Format\n\nOutput ONLY the continuation text — no meta-comme"
    "ntary, no labels, no explanations. The output will be inserted directly after the `[CONT"
    "INUE FROM HERE]` marker.\n\n### User Preferences\n\nConcise prose.\n\n### Do NOT\n\n- Do"
    " NOT change the narrative perspective unless explicitly asked\n- Do NOT add or remove ch"
    "aracters from the scene\n- Do NOT introduce new plot elements not in the KB or recent ch"
    "apters\n- Do NOT over-explain or add exposition not in the original\n- Do NOT repeat or "
    "rephrase the text before the marker\n\n### Constraints\n\n- Write in English\n- Do NOT r"
    'epeat or rephrase the text before the marker\n- Do NOT add meta-commentary (e.g., "Here '
    'is the continuation:", "Continuing from where we left off:")\n- Do NOT introduce new maj'
    "or characters not referenced in the KB or recent chapters\n- Do NOT contradict establish"
    "ed facts from recent chapters\n- If post-text exists after the marker, your continuation"
    " must bridge naturally to it\n- Respect the author's avoidance patterns: Cliches."
)

# Wire-format Tier-5 blocks exactly as T1a's ``_helpers.optional_block`` emits
# them (``"\n\n" + label + ":\n" + text``) — "" when the tier is empty.
_KB_SYSTEMS_BLOCK = "\n\nSystems:\nMagic costs stamina and cannot raise the dead."
_KB_TIMELINES_BLOCK = "\n\nTimelines:\nDay 1: The Fall of Thornwall."
_KB_PINNED_BLOCK = "\n\nPinned context (always included):\nNever kill Elena."

# A2 populated-delta sentinels: raw (render-ready) values for the five KB
# variables the extend route previously assembled but never supplied.
_KB_RELATIONSHIPS_TEXT = "Elena and Mara: uneasy allies since the siege"
_KB_FACTIONS_TEXT = "### Faction: Bridge Wardens"
_KB_OTHER_TEXT = "### Item: Rusty Key"
_KB_SUGGESTED_TEXT = "### Character: Bernd (unaccepted candidate)"
_KB_CONTEXT_WARNINGS_TEXT = "Orphan reference: char-9 (removed entity)"


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

    async def test_empty_tiers_render_byte_identical_to_baseline(self) -> None:
        """KB-empty render MUST equal the R2-C1 baseline golden byte-for-byte."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.EXTEND, _extend_prompt_context())

        assert result.system == _GOLDEN_EMPTY_TIERS_BASELINE
        # Inert by default: no tier labels leak into the prompt.
        assert "Systems:" not in result.system
        assert "Timelines:" not in result.system
        assert "Pinned context" not in result.system
        # R2-C1 render pins: previously-dropped sections render and no
        # level-2 header or unsubstituted placeholder survives.
        for section in (
            "### Output Format",
            "### User Preferences",
            "### Do NOT",
            "### Constraints",
        ):
            assert section in result.system
        assert not any(line.startswith("## ") for line in result.system.splitlines())
        assert "{{" not in result.system

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

    async def test_populated_kb_vars_render_once_at_placeholders(self) -> None:
        """A2 delta: the five previously-unsupplied KB vars render exactly once.

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
        base = _extend_prompt_context()
        prompt_ctx = replace(base, extra={**base.extra, **kb_context_extras(context)})
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.EXTEND, prompt_ctx)

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
        # equals the R2-C1 baseline golden byte-for-byte (supplied-empty is
        # neutral).
        empty_ctx = replace(base, extra={**base.extra, **kb_context_extras(WritingContext())})
        empty_result = await composer.build(LLMIntent.EXTEND, empty_ctx)
        assert empty_result.system == _GOLDEN_EMPTY_TIERS_BASELINE

    async def test_stream_extend_supplies_all_kb_vars_in_extra(self) -> None:
        """A2 wiring: the kb_context_extras merge forwards all ten KB vars.

        Without the merge in pipeline_extend.py, the five previously-unsupplied
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
            mode=GenerationMode.EXTEND,
        )

        async for _chunk in pipeline.generate(request, config=_CONFIG):
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
