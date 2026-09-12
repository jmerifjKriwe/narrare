"""Item-2 — KB enrichment of the write_draft (new_chapter) prompt.

Before item-2 (2026-09-10): ``get_draft_prompt`` built its PromptContext via
``_base_context`` with NO kb extras and no ``chapter_outline`` extra. With a
real ``PromptComposer`` the compose therefore FAILED fast
(``PromptVariableError: kb_characters`` — kb_characters/kb_locations are not
optional on the WRITE route, and ``chapter_outline`` is route-required) —
every existing graph test used mock composers, so the gap was invisible.

Item-2 wires the same enrichment the review step uses into the draft path:
``assemble_writing_context`` (graceful-None, RULE-11) +
``enrich_prompt_context_with_kb`` (full 10-key KB set via the A1 SSOT
``kb_context_extras``) + the route-required ``chapter_outline`` extra.

Golden methodology (mirrors the T1c Tier-5 goldens): the KB-empty constants
below were captured by composing the REAL ``PromptRegistry`` +
``PromptComposer`` route with the exact PromptContext the fixed
``get_draft_prompt`` builds for a KB-empty / no-assembler draft. The template
is untouched by item-2, so KB-empty drafts MUST stay byte-identical — EXCEPT
under R2-A (2026-09-11): the new_chapter template's rogue level-2 headers
("## Output Format", "## Do NOT") were demoted to level-3 (v1.4.0 → v1.5.0),
so the previously-dropped tail region now renders and the goldens were
re-captured for the R2-A header demotion.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from narrare_core.agents.writing_graph_kb_context import enrich_prompt_context_with_kb
from narrare_core.agents.writing_graph_prompts import get_draft_prompt
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.models import WritingContext

_CH_ID = "550e8400-e29b-41d4-a716-446655440000"
_NOVEL_ID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
_OUTLINE = "Elena crosses the flooded bridge at dawn."

# ---------------------------------------------------------------------------
# Golden: KB-empty new_chapter render (captured 2026-09-10 against
# writing/en/new_chapter/system.md v1.4.0; re-captured 2026-09-11 for
# R2-A header demotion — previously-dropped region now renders: the
# former "## Output Format" / "## Do NOT" tails are level-3 headers in
# v1.5.0, so the System Prompt section extends to EOF) via the real
# PromptComposer route; see module docstring for methodology. Do NOT
# hand-edit — recapture mechanically if the template legitimately changes.
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
    "nstructions>Elena crosses the flooded bridge at dawn.</user_instructions>"
    "\nWord target: 1500\nTone: \n\n### Output Format\n\nOutput the complete ch"
    "apter draft as prose. No meta-commentary, no labels, no explanations befor"
    "e or after the text.\n\n### User Preferences\n\n\n\n### Cross-Session Cont"
    "ext\n\nPrevious writing sessions for this project:\n\n\n\n### Do NOT\n\n- "
    "Do NOT change the narrative perspective unless established\n- Do NOT add o"
    "r remove characters not in the outline or KB\n- Do NOT introduce new plot "
    "elements not in the outline\n- Do NOT contradict established facts from re"
    "cent chapters\n\n### Constraints\n\n- Write in English\n- Do not introduce"
    " new major characters not referenced in the outline or KB\n- Do not contra"
    "dict established facts from recent chapters\n- Respect the author's avoida"
    "nce patterns: "
)

_GOLDEN_KB_EMPTY_USER = "Elena crosses the flooded bridge at dawn."

# ---------------------------------------------------------------------------
# Sentinel KB values (raw, render-ready — the assembler emits these formats).
# The three Tier-5 blocks use the exact ``optional_block`` wire format so the
# populated test also guards the value-side label convention.
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
# preference_service + user_id/project_id are wired).
# kb_systems/kb_timelines/kb_pinned have NO placeholders in this template
# at all — supplied-but-unused is ignored by the composer (substitute only
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


class TestDraftPromptKBEmptyGolden:
    """(a)/(c): KB-empty and degraded-assembly drafts render the golden bytes."""

    async def test_draft_without_assembler_renders_kb_empty_golden(self) -> None:
        composer = PromptComposer(PromptRegistry())
        system, user = await get_draft_prompt(composer, _make_deps(composer), _make_state())
        assert system == _GOLDEN_KB_EMPTY_SYSTEM
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_draft_with_empty_kb_context_renders_kb_empty_golden(self) -> None:
        """An assembled but KB-empty WritingContext renders identical bytes."""
        composer = PromptComposer(PromptRegistry())
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(return_value=WritingContext())
        system, user = await get_draft_prompt(
            composer, _make_deps(composer, assembler), _make_state()
        )
        assert system == _GOLDEN_KB_EMPTY_SYSTEM
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_draft_assembly_failure_degrades_to_kb_blind_golden(self) -> None:
        """RULE-11: assembler raises → draft proceeds KB-blind (golden bytes)."""
        composer = PromptComposer(PromptRegistry())
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(side_effect=RuntimeError("DB lost"))
        system, user = await get_draft_prompt(
            composer, _make_deps(composer, assembler), _make_state()
        )
        assert system == _GOLDEN_KB_EMPTY_SYSTEM
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_draft_missing_ids_degrades_to_kb_blind_golden(self) -> None:
        """No chapter_id/novel_id → no assembly → golden bytes."""
        composer = PromptComposer(PromptRegistry())
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(return_value=WritingContext())
        system, user = await get_draft_prompt(
            composer,
            _make_deps(composer, assembler),
            _make_state(chapter_id="", novel_id=""),
        )
        assert system == _GOLDEN_KB_EMPTY_SYSTEM
        assert user == _GOLDEN_KB_EMPTY_USER
        assembler.assemble.assert_not_called()


class TestDraftPromptWordTargetNone:
    """FO-3: word_target=None composes without raising on the real composer.

    Before FO-3 ``word_target`` was supplied only ``if deps.word_target``
    while the new_chapter template demands {{word_target}} unconditionally
    (not in _COMMON_OPTIONAL_VARIABLES) — a draft without a word target
    raised ``PromptVariableError: word_target``. The fix supplies the key
    unconditionally; None renders as an empty value.
    """

    async def test_draft_without_word_target_composes_rendering_empty_value(self) -> None:
        """Real composer: None → no raise; golden with the one-line empty-target delta."""
        composer = PromptComposer(PromptRegistry())
        system, user = await get_draft_prompt(
            composer, _make_deps(composer, word_target=None), _make_state()
        )
        # Explicit pin: the KB-empty golden family with exactly the
        # "Word target: {{word_target}}" line rendered blank.
        assert system == _GOLDEN_KB_EMPTY_SYSTEM.replace("Word target: 1500\n", "Word target: \n")
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_draft_without_word_target_supplies_empty_extra(self) -> None:
        """Wiring: None → extra["word_target"] == "" (key present, value empty)."""
        composer = AsyncMock()
        composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user="u"))
        await get_draft_prompt(composer, _make_deps(composer, word_target=None), _make_state())
        captured = composer.build.call_args.args[1]
        assert captured.extra["word_target"] == ""


class TestDraftPromptPopulatedKB:
    """(b): populated KB values render exactly once at their placeholders."""

    async def test_populated_kb_vars_render_once_at_placeholders(self) -> None:
        composer = PromptComposer(PromptRegistry())
        system, _ = await get_draft_prompt(
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


class TestDraftPromptWiring:
    """Wiring delta: the extras dict carries the full KB set + chapter_outline."""

    async def test_draft_supplies_all_kb_vars_in_extra(self) -> None:
        composer = AsyncMock()
        composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user="u"))
        assembler = _populated_assembler()
        await get_draft_prompt(composer, _make_deps(composer, assembler), _make_state())

        assert assembler.assemble.await_count == 1
        assert assembler.assemble.call_args.kwargs == {
            "chapter_id": UUID(_CH_ID),
            "project_id": UUID(_NOVEL_ID),
            "mode": "full_draft",
        }
        captured = composer.build.call_args.args[1]
        assert isinstance(captured, PromptContext)
        assert captured.mode == "new_chapter"
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

    async def test_draft_without_assembler_degrades_kb_values_to_empty(self) -> None:
        """None assembly → kb_* keys present but "" (KB-blind render).

        Key-level absence would raise PromptVariableError on the real
        composer path (kb_characters/kb_locations are not optional on the
        WRITE route); the pipelines' established degradation pattern is
        value-level — kb_context_extras over an empty WritingContext.
        """
        composer = AsyncMock()
        composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user="u"))
        await get_draft_prompt(composer, _make_deps(composer), _make_state())

        captured = composer.build.call_args.args[1]
        assert captured.extra["chapter_outline"] == _OUTLINE
        assert captured.extra["word_target"] == "1500"
        for name, _sentinel in _RENDERED_SENTINELS:
            if name in ("recent_chapters", "user_preferences", "cross_session_context"):
                assert name not in captured.extra  # empty-field conditionals
            else:
                assert captured.extra[name] == ""


class TestEnrichFullSet:
    """(d): enrich_prompt_context_with_kb supplies the full 10-key SSOT set."""

    def test_enrich_supplies_full_kb_set_coalescing_empty(self) -> None:
        prompt_ctx = PromptContext(language="en", genre="fantasy", tone="balanced")
        prompt_ctx.extra = {"word_target": "1000"}
        enrich_prompt_context_with_kb(prompt_ctx, WritingContext(kb_characters="Elena"))

        expected_all = {
            "kb_characters": "Elena",
            "kb_locations": "",
            "kb_factions": "",
            "kb_other": "",
            "kb_relationships": "",
            "kb_suggested": "",
            "kb_systems": "",
            "kb_timelines": "",
            "kb_pinned": "",
            "kb_context_warnings": "",
        }
        assert {k: prompt_ctx.extra[k] for k in expected_all} == expected_all
        # Non-kb extras untouched; empty non-kb fields still skipped.
        assert prompt_ctx.extra["word_target"] == "1000"
        assert "recent_chapters" not in prompt_ctx.extra
        assert "user_preferences" not in prompt_ctx.extra
        assert "cross_session_context" not in prompt_ctx.extra
