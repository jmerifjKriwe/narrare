"""Item-2 follow-up — KB enrichment of the revise_draft (new_chapter) prompt.

Before this fix (2026-09-10): ``get_revise_prompt`` had the identical gap the
write_draft path had (fixed in commit ac55a094) — no KB enrichment and no
``chapter_outline``/``word_target`` supply. The REWRITE route resolves its
context mode ``new_chapter`` onto the new_chapter template (REWRITE declares
no ``allowed_context_modes``, so the context mode overrides the default
``rewrite_selection`` template), where ``kb_characters`` / ``kb_locations`` /
``chapter_outline`` / ``word_target`` are NOT route-optional. With a real
``PromptComposer`` the compose therefore FAILED fast
(``PromptVariableError: kb_characters``) — every existing graph test used
mock composers, so the gap was invisible.

The fix wires the same enrichment the draft step uses into the revise path:
``_assemble_writing_context`` (graceful-None, RULE-11) +
``_enrich_prompt_context_with_kb`` (full 10-key KB set via the SSOT
``kb_context_extras``) + the ``chapter_outline`` extra.

Golden methodology (mirrors the item-2 draft goldens): the KB-empty constants
below were captured by composing the REAL ``PromptRegistry`` +
``PromptComposer`` route with the exact PromptContext the fixed
``get_revise_prompt`` builds for a KB-empty / no-assembler revision. The
template is untouched by this fix, so KB-empty revisions MUST stay
byte-identical — EXCEPT under R2-A (2026-09-11): the new_chapter template's
rogue level-2 headers ("## Output Format", "## Do NOT") were demoted to
level-3 (v1.4.0 → v1.5.0), so the previously-dropped tail region now renders
and the goldens were re-captured for the R2-A header demotion (user channel
unchanged at 152 B).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from narrare_core.agents.writing_graph_prompts import get_revise_prompt
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.models import WritingContext

_CH_ID = "550e8400-e29b-41d4-a716-446655440000"
_NOVEL_ID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
_OUTLINE = "Elena crosses the flooded bridge at dawn."
_FEEDBACK = "Tighten the bridge crossing; cut the weather digression."
_DRAFT = "Elena walked onto the flooded bridge. The rain had gone on for days."
_REVISE_CONTENT = f"Revise based on feedback: {_FEEDBACK}\n\n{_DRAFT}"

# ---------------------------------------------------------------------------
# Golden: KB-empty new_chapter render (captured 2026-09-10 against
# writing/en/new_chapter/system.md v1.4.0; re-captured 2026-09-11 for
# R2-A header demotion — previously-dropped region now renders: the
# former "## Output Format" / "## Do NOT" tails are level-3 headers in
# v1.5.0, so the System Prompt section extends to EOF) via the real
# PromptComposer route [REWRITE intent, context-mode override
# "new_chapter"]; see module docstring for methodology. Do NOT hand-edit —
# recapture mechanically if the template legitimately changes.
# ---------------------------------------------------------------------------

_GOLDEN_KB_EMPTY_SYSTEM = (
    "You are a skilled creative writing assistant helping an author generate ne"
    "w chapter content. Your role is to produce polished, engaging prose that r"
    "espects the author's established voice, world, and characters.\n\n\n\n### "
    "Context\n\n- Project: \n- Genre: fantasy\n- Language: English\n- Timeline:"
    " \n- **Story Structure**: \n\n### Knowledge Base\n\n\nCharacters:\n\n\nLoc"
    "ations:\n\n\nFactions:\n\n\nOther entities:\n\n\nRelationships:\n\n\n### S"
    "uggested KB Entries\n\nOptional lower-priority generated KB suggestions. T"
    "hese are unaccepted candidates.\nUse them only when they support the curre"
    "nt author instructions, project writing\nprofile, current scene/timeline c"
    "ontext, and curated KB. They must not override\ncurrent author instruction"
    "s, the project profile, current scene/timeline context,\nor curated KB.\n"
    "\n\n\n### Recent Chapters\n\n\n\n### Series History\n\nFor novels that are"
    " part of a series, this block summarises what happened in\nthe preceding b"
    "ands. Use it to preserve continuity of plot, world state, and\ncharacter a"
    "rcs across the series. It is empty for standalone novels.\n\n\n\n### Story"
    " Synopsis\n\n\n\n### Style Profile\n\nThe author's established writing sty"
    "le:\n\n\n\n### Character Voice Profiles\n\nWhen writing dialogue, maintain"
    " each character's distinct voice based on their speech patterns:\n\n\n\n**"
    "Voice consistency rules:**\n- Each character must use their established di"
    "alect, vocabulary, and verbal tics\n- Match their personality traits when "
    "they speak (formal, casual, terse, eloquent)\n- Characters should be ident"
    "ifiable by their speech alone, without dialogue tags\n- Do NOT make all ch"
    "aracters sound the same — preserve their linguistic individuality\n\n### A"
    "uthor Voice\n\nThe narrator's prose voice for this novel (descriptive prof"
    "ile, not raw metrics):\n\n\n\n### Instructions\n\nWrite a complete chapter"
    " draft based on the outline and context provided. Follow these guidelines:"
    "\n\n1. Match the author's established style and tone from recent chapters"
    "\n2. Maintain consistency with all referenced characters, locations, and p"
    "lot points\n3. Use natural dialogue that reflects each character's voice\n"
    "4. Weave setting details organically into the narrative\n5. Respect pacing"
    " — balance action, dialogue, description, and reflection\n\nChapter outlin"
    "e: Elena crosses the flooded bridge at dawn.\nAuthor instructions: <user_i"
    "nstructions>Tighten the bridge crossing; cut the weather digression.</user"
    "_instructions>\nWord target: 1500\nTone: \n\n### Output Format\n\nOutput t"
    "he complete chapter draft as prose. No meta-commentary, no labels, no expl"
    "anations before or after the text.\n\n### User Preferences\n\n\n\n### Cros"
    "s-Session Context\n\nPrevious writing sessions for this project:\n\n\n\n##"
    "# Do NOT\n\n- Do NOT change the narrative perspective unless established\n"
    "- Do NOT add or remove characters not in the outline or KB\n- Do NOT intro"
    "duce new plot elements not in the outline\n- Do NOT contradict established"
    " facts from recent chapters\n\n### Constraints\n\n- Write in English\n- Do"
    " not introduce new major characters not referenced in the outline or KB\n-"
    " Do not contradict established facts from recent chapters\n- Respect the a"
    "uthor's avoidance patterns: "
)

_GOLDEN_KB_EMPTY_USER = (
    "Revise based on feedback: Tighten the bridge crossing; cut the wea"
    "ther digression.\n\nElena walked onto the flooded bridge. The rain h"
    "ad gone on for days."
)

# ---------------------------------------------------------------------------
# Sentinel KB values (raw, render-ready — the assembler emits these formats).
# ---------------------------------------------------------------------------

_KB_CHARACTERS = "### Character: Elena"
_KB_LOCATIONS = "### Location: Flooded Bridge"
_KB_FACTIONS = "### Faction: Bridge Wardens"
_KB_OTHER = "### Item: Rusty Key"
_KB_RELATIONSHIPS = "Elena → [ally of] → Mara"
_KB_SUGGESTED = "### Character: Bernd (unaccepted candidate)"
_KB_SYSTEMS_BLOCK = "\n\nSystems:\nMagic costs stamina and cannot raise the dead."
_KB_TIMELINES_BLOCK = "\n\nTimelines:\nDay 1: The Fall of Thornwall."
_KB_PINNED_BLOCK = "\n\nPinned context (always included):\nNever kill Elena."
_KB_CONTEXT_WARNINGS = "Orphan reference: char-9 (removed entity)"
_RECENT_CHAPTERS = "Chapter 1: The hero arrived."
_USER_PREFERENCES = "Avoid excessive adjectives."
_CROSS_SESSION_CONTEXT = "Session 4 ended mid-storm; the author prefers slow tension builds."

# Placeholders the new_chapter template's RENDERED "## System Prompt"
# section actually carries. Since the R2-A header demotion (v1.5.0) the
# System Prompt section extends to EOF, so {{user_preferences}} and
# {{cross_session_context}} render too (wiring below supplies them via
# the enrichment extras). {{avoidance_patterns}} renders but stays empty
# on the graph path — no graph enrichment supplies it and the graph's
# PromptContext keeps the dataclass default "" (the composer's
# preference auto-injection only fills user_preferences, and only when a
# preference_service + user_id/project_id are wired). kb_systems/
# kb_timelines/kb_pinned have NO placeholders in this template at all —
# supplied-but-unused is ignored by the composer (substitute only
# replaces found placeholders).
_RENDERED_SENTINELS: tuple[tuple[str, str], ...] = (
    ("kb_context_warnings", _KB_CONTEXT_WARNINGS),
    ("kb_characters", _KB_CHARACTERS),
    ("kb_locations", _KB_LOCATIONS),
    ("kb_factions", _KB_FACTIONS),
    ("kb_other", _KB_OTHER),
    ("kb_relationships", _KB_RELATIONSHIPS),
    ("kb_suggested", _KB_SUGGESTED),
    ("recent_chapters", _RECENT_CHAPTERS),
    ("user_preferences", _USER_PREFERENCES),
    ("cross_session_context", _CROSS_SESSION_CONTEXT),
)
_UNUSED_SENTINELS: tuple[str, ...] = (_KB_SYSTEMS_BLOCK, _KB_TIMELINES_BLOCK, _KB_PINNED_BLOCK)


def _make_deps(composer: Any, assembler: Any = None, word_target: int | None = 1500) -> WritingDeps:
    return WritingDeps(
        registry=AsyncMock(),
        composer=composer,
        genre="fantasy",
        tone="balanced",
        word_target=word_target,
        language="en",
        writing_language="English",
        context_assembler=assembler,
    )


def _make_state(**overrides: Any) -> WritingState:
    defaults: dict[str, Any] = {
        "chapter_id": _CH_ID,
        "novel_id": _NOVEL_ID,
        "outline": _OUTLINE,
        "draft": _DRAFT,
        "feedback": _FEEDBACK,
    }
    defaults.update(overrides)
    return WritingState(**defaults)


def _populated_assembler() -> MagicMock:
    assembler = MagicMock(spec=WritingContextAssembler)
    assembler.assemble = AsyncMock(
        return_value=WritingContext(
            kb_characters=_KB_CHARACTERS,
            kb_locations=_KB_LOCATIONS,
            kb_factions=_KB_FACTIONS,
            kb_other=_KB_OTHER,
            kb_relationships=_KB_RELATIONSHIPS,
            kb_suggested=_KB_SUGGESTED,
            kb_systems=_KB_SYSTEMS_BLOCK,
            kb_timelines=_KB_TIMELINES_BLOCK,
            kb_pinned=_KB_PINNED_BLOCK,
            kb_context_warnings=_KB_CONTEXT_WARNINGS,
            recent_chapters=_RECENT_CHAPTERS,
            user_preferences=_USER_PREFERENCES,
            cross_session_context=_CROSS_SESSION_CONTEXT,
        )
    )
    return assembler


class TestRevisePromptKBEmptyGolden:
    """KB-empty and degraded-assembly revisions render the golden bytes."""

    async def test_revise_without_assembler_renders_kb_empty_golden(self) -> None:
        composer = PromptComposer(PromptRegistry())
        system, user = await get_revise_prompt(composer, _make_deps(composer), _make_state())
        assert system == _GOLDEN_KB_EMPTY_SYSTEM
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_revise_with_empty_kb_context_renders_kb_empty_golden(self) -> None:
        """An assembled but KB-empty WritingContext renders identical bytes."""
        composer = PromptComposer(PromptRegistry())
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(return_value=WritingContext())
        system, user = await get_revise_prompt(
            composer, _make_deps(composer, assembler), _make_state()
        )
        assert system == _GOLDEN_KB_EMPTY_SYSTEM
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_revise_assembly_failure_degrades_to_kb_blind_golden(self) -> None:
        """RULE-11: assembler raises → revision proceeds KB-blind (golden bytes)."""
        composer = PromptComposer(PromptRegistry())
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(side_effect=RuntimeError("DB lost"))
        system, user = await get_revise_prompt(
            composer, _make_deps(composer, assembler), _make_state()
        )
        assert system == _GOLDEN_KB_EMPTY_SYSTEM
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_revise_missing_ids_degrades_to_kb_blind_golden(self) -> None:
        """No chapter_id/novel_id → no assembly → golden bytes."""
        composer = PromptComposer(PromptRegistry())
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(return_value=WritingContext())
        system, user = await get_revise_prompt(
            composer,
            _make_deps(composer, assembler),
            _make_state(chapter_id="", novel_id=""),
        )
        assert system == _GOLDEN_KB_EMPTY_SYSTEM
        assert user == _GOLDEN_KB_EMPTY_USER
        assembler.assemble.assert_not_called()


class TestRevisePromptWordTargetNone:
    """FO-3: word_target=None composes without raising on the real composer.

    Before FO-3 ``word_target`` was supplied only ``if deps.word_target``
    while the REWRITE route renders the new_chapter template via its
    context-mode override, where {{word_target}} is not route-optional —
    a revision without a word target raised ``PromptVariableError:
    word_target`` (same masked-by-mocks defect class as the draft path).
    """

    async def test_revise_without_word_target_composes_rendering_empty_value(self) -> None:
        """Real composer: None → no raise; golden with the one-line empty-target delta."""
        composer = PromptComposer(PromptRegistry())
        system, user = await get_revise_prompt(
            composer, _make_deps(composer, word_target=None), _make_state()
        )
        # Explicit pin: the KB-empty golden family with exactly the
        # "Word target: {{word_target}}" line rendered blank.
        assert system == _GOLDEN_KB_EMPTY_SYSTEM.replace("Word target: 1500\n", "Word target: \n")
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_revise_without_word_target_supplies_empty_extra(self) -> None:
        """Wiring: None → extra["word_target"] == "" (key present, value empty)."""
        composer = AsyncMock()
        composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user="u"))
        await get_revise_prompt(composer, _make_deps(composer, word_target=None), _make_state())
        captured = composer.build.call_args.args[1]
        assert captured.extra["word_target"] == ""


class TestRevisePromptPopulatedKB:
    """Populated KB values render exactly once at their placeholders."""

    async def test_populated_kb_vars_render_once_at_placeholders(self) -> None:
        composer = PromptComposer(PromptRegistry())
        system, user = await get_revise_prompt(
            composer,
            _make_deps(composer, _populated_assembler()),
            _make_state(),
        )
        for _name, sentinel in _RENDERED_SENTINELS:
            assert system.count(sentinel) == 1, f"{sentinel!r} must render exactly once"
        # Static template labels unchanged, values directly under them.
        assert f"Characters:\n{_KB_CHARACTERS}" in system
        assert f"Locations:\n{_KB_LOCATIONS}" in system
        assert f"Factions:\n{_KB_FACTIONS}" in system
        assert f"Other entities:\n{_KB_OTHER}" in system
        assert f"Relationships:\n{_KB_RELATIONSHIPS}" in system
        # R2-A: the previously-dropped region now renders its vars —
        # user_preferences and cross_session_context land at their
        # placeholders (value-side, under the level-3 section headers),
        # avoidance_patterns substitutes empty (graph path supplies no
        # value; PromptContext dataclass default "").
        assert f"### User Preferences\n\n{_USER_PREFERENCES}" in system
        assert f"Previous writing sessions for this project:\n\n{_CROSS_SESSION_CONTEXT}" in system
        assert system.endswith("- Respect the author's avoidance patterns: ")
        # Supplied-but-unused extras (no placeholders in this template) are
        # ignored by the composer — Tier-5 blocks must NOT leak.
        for block in _UNUSED_SENTINELS:
            assert block not in system
        # No unsubstituted placeholder survives composition.
        assert "{{" not in system
        # The user channel stays the feedback+draft revise content — KB
        # values never leak into the user prompt.
        assert user == _REVISE_CONTENT


class TestRevisePromptWiring:
    """Wiring delta: the extras dict carries the full KB set + chapter_outline."""

    async def test_revise_supplies_all_kb_vars_in_extra(self) -> None:
        composer = AsyncMock()
        composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user="u"))
        assembler = _populated_assembler()
        await get_revise_prompt(composer, _make_deps(composer, assembler), _make_state())

        assert assembler.assemble.await_count == 1
        assert assembler.assemble.call_args.kwargs == {
            "chapter_id": UUID(_CH_ID),
            "project_id": UUID(_NOVEL_ID),
            "mode": "full_draft",
        }
        assert composer.build.call_args.args == (
            LLMIntent.REWRITE,
            composer.build.call_args.args[1],
        )
        assert composer.build.call_args.kwargs == {"user_prompt": _REVISE_CONTENT}
        captured = composer.build.call_args.args[1]
        assert isinstance(captured, PromptContext)
        assert captured.mode == "new_chapter"
        assert captured.author_instructions == _FEEDBACK
        assert captured.existing_content == _DRAFT
        assert captured.extra["chapter_outline"] == _OUTLINE
        assert captured.extra["word_target"] == "1500"
        for name, sentinel in _RENDERED_SENTINELS:
            assert captured.extra[name] == sentinel
        # Enrichment conditionals reach the render surface since R2-A —
        # user_preferences and cross_session_context placeholders now live
        # inside the rendered System Prompt section (route-independent
        # enrich contract preserved).
        assert captured.extra["user_preferences"] == _USER_PREFERENCES
        assert captured.extra["cross_session_context"] == _CROSS_SESSION_CONTEXT

    async def test_revise_without_assembler_degrades_kb_values_to_empty(self) -> None:
        """None assembly → kb_* keys present but "" (KB-blind render).

        Key-level absence would raise PromptVariableError on the real
        composer path (kb_characters/kb_locations are not optional on the
        new_chapter template this route renders); the established
        degradation pattern is value-level — kb_context_extras over an
        empty WritingContext.
        """
        composer = AsyncMock()
        composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user="u"))
        await get_revise_prompt(composer, _make_deps(composer), _make_state())

        captured = composer.build.call_args.args[1]
        assert captured.extra["chapter_outline"] == _OUTLINE
        assert captured.extra["word_target"] == "1500"
        for name, _sentinel in _RENDERED_SENTINELS:
            if name in ("recent_chapters", "user_preferences", "cross_session_context"):
                assert name not in captured.extra  # empty-field conditionals
            else:
                assert captured.extra[name] == ""
