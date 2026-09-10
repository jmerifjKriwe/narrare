"""Tier-5 KB injection — scene_by_scene route render tests (slice T1f).

Separate file (RULE-04): the shared ``test_tier5_injection.py`` landed at
301 lines with T1c; appending the T1f class would exceed the 400-line hard
limit — same separate-file precedent as T1d (rewrite_selection, 254 lines)
and T1e (co_author).

Invariant under test
--------------------
The three Tier-5 variables (``{{kb_systems}}``, ``{{kb_timelines}}``,
``{{kb_pinned}}``) are appended DIRECTLY to the existing
``{{kb_relationships}}`` template line — zero new template lines. The context
assembler (T1a, ``_helpers.optional_block``) supplies value-side labeled
blocks (``"\\n\\n<Label>:\\n<text>"``) or ``""`` for empty tiers, so:

* KB-empty novels render BYTE-IDENTICALLY to the pre-T1f prompt (golden), and
* populated tiers render their labeled blocks in fixed order after
  ``Relationships:``.

Route-composition fix (T1f)
---------------------------
``pipeline_scene.py`` passed ``mode="scene"`` to ``_build_prompt_context``,
but WRITE's governed context-modes are ``new_chapter`` / ``scene_by_scene`` /
``interview`` / ``interactive_session`` (route_table.py), so the real
composition raised ``PromptRouteNotConfiguredError``. The golden below was
therefore captured with the FIXED mode ``scene_by_scene`` against the
pre-T1f template (prompt_version 1.3.0, git HEAD via a shadow bundled tree,
rendered under identical composer/context conditions).

Item-3 (2026-09-10): the template gained the scene numbering line
``Scene {{scene_number}} of {{total_scenes}}.`` (prompt_version 1.5.0);
both vars are SYSTEM_VARS supplied via ``extra_overrides``, the redundant
``scene_outline`` extra was removed, and the golden was re-captured (see
the provenance note at the constant). Numbering render tests live in
``test_scene_numbering.py`` (RULE-04 split).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.errors import PromptRouteNotConfiguredError
from narrare_core.writing import GenerationMode
from narrare_core.writing._helpers import kb_context_extras
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline

# ---------------------------------------------------------------------------
# Golden: WRITE/scene_by_scene system prompt with ALL Tier-5 kb values empty
# (the KB-empty novel case).
#
# Provenance: originally captured 2026-09-10 (slice T1f) with the FIXED route
# mode ``scene_by_scene`` — the pre-fix ``mode="scene"`` raises
# PromptRouteNotConfiguredError (see module docstring) — against the pre-T1f
# template (prompt_version 1.3.0, 2352 bytes).
#
# RE-CAPTURED 2026-09-10 for item-3: the template (prompt_version 1.4.0 →
# 1.5.0) adds the scene numbering line ``Scene {{scene_number}} of
# {{total_scenes}}.`` after the task statement, and the helper below now
# mirrors the pipeline's item-3 extras (scene_number="1", total_scenes="2" —
# the first scene of the two-scene outline). Recaptured mechanically with the
# real PromptRegistry + PromptComposer under identical composer/context
# conditions (2367 bytes). Empty-tier byte-identity is now asserted relative
# to THIS baseline, not the pre-T1f render. Do NOT hand-edit — if the
# template legitimately changes, recapture mechanically and update this note.
# ---------------------------------------------------------------------------

_GOLDEN_EMPTY_TIERS_BASELINE = (
    "You are a skilled creative writing assistant helping an author generate chapter content scene "
    "by scene. Your role is to produce one scene at a time, waiting for the author's signal before "
    "continuing.\n\nScene 1 of 2.\n\n\n\n### Context\n\n- Project: Test Novel\n- Genre: fantasy\n- "
    "Language: English\n- Timeline: \n- **Story Structure**: \n\n### Knowledge Base\n\n\nCharacters"
    ":\n\n\nLocations:\n\n\nFactions:\n\n\nOther entities:\n\n\nRelationships:\n\n\n### Suggested K"
    "B Entries\n\nOptional lower-priority generated KB suggestions. These are unaccepted candidates"
    ".\nUse them only when they support the current author instructions, project writing\nprofile, "
    "current scene/timeline context, and curated KB. They must not override\ncurrent author instruc"
    "tions, the project profile, current scene/timeline context,\nor curated KB.\n\n\n\n### Recent "
    "Chapters\n\n\n\n### Story Synopsis\n\n\n\n### Style Profile\n\nThe author's established writin"
    "g style:\n\n\n\n### Character Voice Profiles\n\nWhen writing dialogue, maintain each character"
    "'s distinct voice based on their speech patterns:\n\nElena: formal, terse.\n\n**Voice consiste"
    "ncy rules:**\n- Each character must use their established dialect, vocabulary, and verbal tics"
    "\n- Match their personality traits when they speak (formal, casual, terse, eloquent)\n- Charac"
    "ters should be identifiable by their speech alone, without dialogue tags\n- Do NOT make all ch"
    "aracters sound the same — preserve their linguistic individuality\n\n### Author Voice\n\nThe n"
    "arrator's prose voice for this novel (descriptive profile, not raw metrics):\n\nLyrical, close"
    " third person.\n\n### Instructions\n\nGenerate ONE scene at a time from the chapter outline. F"
    "ollow these guidelines:\n\n1. Each scene should be a self-contained narrative unit\n2. Separat"
    'e scenes with a scene break marker: `***`\n3. Wait for the author\'s signal (e.g. "continue", '
    '"next scene") before generating the next scene\n4. Match the established style from recent cha'
    "pters\n5. End each scene at a natural break point — never mid-action unless cliffhanger is app"
    "ropriate\n\nChapter outline: Bridge chapter in two scenes.\nAuthor instructions: <user_instruc"
    "tions>The bridge at night, rain on the river.</user_instructions>\nWord target per scene: 400"
    "\nTone: \n\nScene-by-scene approach:\n- Identify the key beats for each scene from the outline"
    "\n- Build each scene around its central moment or turning point\n- Ensure smooth transitions b"
    "etween scenes"
)

# Wire-format Tier-5 blocks exactly as T1a's ``_helpers.optional_block`` emits
# them (``"\n\n" + label + ":\n" + text``) — "" when the tier is empty.
_KB_SYSTEMS_BLOCK = "\n\nSystems:\nMagic costs stamina and cannot raise the dead."
_KB_TIMELINES_BLOCK = "\n\nTimelines:\nDay 1: The Fall of Thornwall."
_KB_PINNED_BLOCK = "\n\nPinned context (always included):\nNever kill Elena."

# A2 populated-delta sentinels: raw (render-ready) values for the five KB
# variables the scene route previously assembled but never supplied (they
# flow via WritingPipeline._build_prompt_context, not pipeline_scene.py).
_KB_RELATIONSHIPS_TEXT = "Elena and Mara: uneasy allies since the siege"
_KB_FACTIONS_TEXT = "### Faction: Bridge Wardens"
_KB_OTHER_TEXT = "### Item: Rusty Key"
_KB_SUGGESTED_TEXT = "### Character: Bernd (unaccepted candidate)"
_KB_CONTEXT_WARNINGS_TEXT = "Orphan reference: char-9 (removed entity)"


def _scene_prompt_context(
    *,
    kb_systems: str = "",
    kb_timelines: str = "",
    kb_pinned: str = "",
    scene_number: str = "1",
    total_scenes: str = "2",
) -> PromptContext:
    """Build the WRITE/scene_by_scene PromptContext the scene route builds.

    Mirrors ``WritingPipeline._build_prompt_context`` (pipeline.py, incl. the
    T1f Tier-5 kb extra keys) as invoked by ``stream_scene_by_scene`` with the
    fixed route mode, so the composition tests exercise the real route surface
    rather than a hand-rolled variable set. Item-3: the scene-position extras
    (``scene_number`` / ``total_scenes``) mirror the pipeline's
    ``extra_overrides`` — first scene of the two-scene outline by default.
    """
    return PromptContext(
        language="en",
        writing_language="English",
        project_title="Test Novel",
        genre="fantasy",
        tone="balanced",
        mode="scene_by_scene",
        existing_content="",
        author_instructions="The bridge at night, rain on the river.",
        user_preferences="Concise prose.",
        avoidance_patterns="Cliches.",
        cross_session_context="",
        character_voice_profiles="Elena: formal, terse.",
        author_voice="Lyrical, close third person.",
        extra={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "project_id": "00000000-0000-0000-0000-000000000002",
            "chapter_outline": "Bridge chapter in two scenes.",
            "kb_characters": "",
            "kb_locations": "",
            "kb_systems": kb_systems,
            "kb_timelines": kb_timelines,
            "kb_pinned": kb_pinned,
            "recent_chapters": "",
            "character_voice_profiles": "Elena: formal, terse.",
            "author_voice": "Lyrical, close third person.",
            "series_history": "",
            "word_target": "400",
            # TONE_INSTRUCTIONS["balanced"] == "" (faithful to the default path)
            "tone_instructions": "",
            "writing_language": "English",
            # Item-3: scene-position extras (pipeline_scene.py extra_overrides)
            "scene_number": scene_number,
            "total_scenes": total_scenes,
        },
    )


_CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model", max_tokens=2000)
_USAGE = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


async def _final_only_stream() -> AsyncIterator[StreamChunk]:
    yield StreamChunk(text="", is_final=True, usage=_USAGE)


class TestTier5InjectionScene:
    """scene_by_scene (T1f): Tier-5 vars render inert when empty, labeled when populated."""

    async def test_empty_tiers_render_byte_identical_to_baseline(self) -> None:
        """KB-empty render MUST equal the item-3 baseline golden byte-for-byte."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.WRITE, _scene_prompt_context())

        assert result.system == _GOLDEN_EMPTY_TIERS_BASELINE
        # Inert by default: no tier labels leak into the prompt.
        assert "Systems:" not in result.system
        assert "Timelines:" not in result.system
        assert "Pinned context" not in result.system
        # No unsubstituted placeholder survives composition.
        assert "{{kb_" not in result.system
        assert "{{scene_" not in result.system

    async def test_populated_tiers_render_labeled_blocks_after_relationships(self) -> None:
        """Populated tiers render their labeled blocks in order after 'Relationships:'."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(
            LLMIntent.WRITE,
            _scene_prompt_context(
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

    async def test_stream_scene_supplies_tier5_vars_in_extra(self) -> None:
        """stream_scene_by_scene forwards Tier-5 blocks + the fixed route mode.

        Guards the pipeline wiring (pipeline.py ``_build_prompt_context`` +
        the pipeline_scene.py route-composition fix): without the three keys,
        populated tiers would silently render "" via the route's
        optional-variable fallback (RULE-11); with the old ``mode="scene"``
        the real composition would raise PromptRouteNotConfiguredError.
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
                chapter_outline="Single bridge scene outline.",
                word_target=400,
                kb_systems=_KB_SYSTEMS_BLOCK,
                kb_timelines=_KB_TIMELINES_BLOCK,
                kb_pinned=_KB_PINNED_BLOCK,
            )
        )
        registry = MagicMock(spec=["stream", "run"])
        registry.stream = MagicMock(spec=[], side_effect=lambda **kw: _final_only_stream())
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
            mode=GenerationMode.SCENE_BY_SCENE,
            outline="Single bridge scene outline.",
        )

        async for _chunk in pipeline.generate(request, config=_CONFIG):
            pass

        prompt_ctx = composer.build.call_args.args[1]
        assert prompt_ctx.mode == "scene_by_scene"
        extra: dict[str, Any] = prompt_ctx.extra
        assert extra["kb_systems"] == _KB_SYSTEMS_BLOCK
        assert extra["kb_timelines"] == _KB_TIMELINES_BLOCK
        assert extra["kb_pinned"] == _KB_PINNED_BLOCK
        # Item-3: scene-position extras are forwarded (single-scene outline →
        # 1 of 1) and the redundant scene_outline extra is gone (the outline
        # flows as author_instructions; the var exists in no registry or
        # template — it was supplied-but-unrendered dead data).
        assert extra["scene_number"] == "1"
        assert extra["total_scenes"] == "1"
        assert "scene_outline" not in extra

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
        base = _scene_prompt_context()
        prompt_ctx = replace(base, extra={**base.extra, **kb_context_extras(context)})
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.WRITE, prompt_ctx)

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
        # equals the empty-tiers baseline golden byte-for-byte
        # (supplied-empty is neutral; scene extras ride in via base.extra).
        empty_ctx = replace(base, extra={**base.extra, **kb_context_extras(WritingContext())})
        empty_result = await composer.build(LLMIntent.WRITE, empty_ctx)
        assert empty_result.system == _GOLDEN_EMPTY_TIERS_BASELINE

    async def test_stream_scene_supplies_all_kb_vars_in_extra(self) -> None:
        """A2 wiring: the kb_context_extras merge forwards all ten KB vars.

        Without the merge in pipeline.py ``_build_prompt_context`` (which the
        scene route inherits), the five previously-unsupplied variables would
        silently render "" via the optional-variable fallback (RULE-11).
        """
        composer = MagicMock(spec=PromptComposer)
        composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(
            return_value=WritingContext(
                chapter_outline="Single bridge scene outline.",
                word_target=400,
                kb_relationships=_KB_RELATIONSHIPS_TEXT,
                kb_factions=_KB_FACTIONS_TEXT,
                kb_other=_KB_OTHER_TEXT,
                kb_suggested=_KB_SUGGESTED_TEXT,
                kb_context_warnings=_KB_CONTEXT_WARNINGS_TEXT,
            )
        )
        registry = MagicMock(spec=["stream", "run"])
        registry.stream = MagicMock(spec=[], side_effect=lambda **kw: _final_only_stream())
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
            mode=GenerationMode.SCENE_BY_SCENE,
            outline="Single bridge scene outline.",
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

    def test_scene_route_mode_is_governed(self) -> None:
        """Regression for the T1f route-composition fix.

        ``scene_by_scene`` must resolve as a governed WRITE context-mode —
        the pipeline previously passed ``mode="scene"``, which is NOT in
        WRITE's ``allowed_context_modes`` and made ``resolve_prompt_route``
        raise ``PromptRouteNotConfiguredError`` on the real compose path.
        """
        route = resolve_prompt_route(LLMIntent.WRITE, "scene_by_scene")
        assert (route.category, route.mode) == ("writing", "scene_by_scene")

        with pytest.raises(PromptRouteNotConfiguredError):
            resolve_prompt_route(LLMIntent.WRITE, "scene")
