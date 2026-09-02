"""Real-composer regression tests for KB assist intent→template-mode routing.

Found by the Task-1b review (pre-existing bug moved verbatim in commit
72fbfc38): ``_assist_context._INTENT_MAP`` was doubly broken — its keys
were plain strings (``"interview"``) looked up with an ``LLMIntent``
enum argument (never matching), and its values were the enum members
whose ``.value`` (``"kb_interview"``) is a model-routing identifier, NOT
a governed kb template mode. Net effect: ``PromptContext.mode`` always
collapsed to ``"kb_interview"`` → ``PromptNotFoundError`` for the
non-existent ``kb/en/kb_interview`` template in every real (unmocked)
composition — invisible to mock-based unit tests.

Contract pinned here: all three assist intents must map to their
governed template modes per ``route_table.py`` (kb category) and those
templates must exist on disk and resolve through the real
``PromptRegistry`` — the exact composition stage that failed pre-fix.

Note: full end-to-end ``composer.build()`` additionally requires the
``template_structure`` / ``world_context`` variables, which
``build_prompt_context`` does not thread today (separate pre-existing
gap — tracked independently); these tests pin the mode-routing stage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from narrare.kb._assist_context import build_prompt_context
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts import PromptRegistry
from narrare_core.prompts.routes import resolve_prompt_route

_BUNDLED = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "core"
    / "narrare_core"
    / "prompts"
    / "_bundled"
    / "kb"
    / "en"
)

#: intent → governed kb template mode (route_table.py, kb category).
_GOVERNED_MODES: dict[LLMIntent, str] = {
    LLMIntent.KB_INTERVIEW: "interview",
    LLMIntent.KB_SUGGEST: "suggest",
    LLMIntent.KB_ENHANCE: "enhance",
}

_ASSIST_INTENTS: list[tuple[LLMIntent, str]] = list(_GOVERNED_MODES.items())

#: Non-mode enum values that the pre-fix bug collapsed every intent to.
_UNGOVERNED_ENUM_VALUES = frozenset({"kb_interview", "kb_suggest", "kb_enhance"})


@pytest.fixture(scope="module")
def registry() -> PromptRegistry:
    return PromptRegistry()


@pytest.mark.parametrize(("intent", "expected_mode"), _ASSIST_INTENTS)
def test_build_prompt_context_maps_intent_to_governed_template_mode(
    intent: LLMIntent,
    expected_mode: str,
) -> None:
    """Each assist intent's context mode is the governed template mode."""
    ctx = build_prompt_context(intent, "character", {"name": "Alice"})

    assert ctx.mode == expected_mode
    # Regression: the mode must never be the raw LLMIntent enum value.
    assert ctx.mode not in _UNGOVERNED_ENUM_VALUES


@pytest.mark.mutation_inert
@pytest.mark.parametrize("mode", sorted(_GOVERNED_MODES.values()))
def test_governed_assist_template_exists_on_disk(mode: str) -> None:
    """The governed kb template for each assist mode exists in _bundled.

    ``mutation_inert``: pure asset-structure assertion reached via
    ``parents[4]`` — the path does not exist inside MutMut's sandbox
    (see test_kb_avoidance_slot_removal.py for the full rationale).
    """
    assert (_BUNDLED / mode / "system.md").is_file(), (
        f"Governed kb template kb/en/{mode}/system.md must exist on disk."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("intent", "expected_mode"), _ASSIST_INTENTS)
async def test_assist_intent_resolves_governed_template_through_real_registry(
    intent: LLMIntent,
    expected_mode: str,
    registry: PromptRegistry,
) -> None:
    """The intent's context mode routes and resolves through the real composer stages.

    Exercises the exact stages of ``PromptComposer.build`` that raised
    ``PromptNotFoundError`` pre-fix: ``resolve_prompt_route`` (real route
    governance) followed by ``PromptRegistry.resolve`` (real template
    lookup). No compose_invocation mock involved.
    """
    ctx = build_prompt_context(intent, "character", {"name": "Alice"})

    route = resolve_prompt_route(intent, ctx.mode)
    assert route.category == "kb"
    assert route.mode == expected_mode

    resolved = await registry.resolve(
        category=route.category,
        language=ctx.language,
        mode=route.mode,
    )
    assert resolved.system_prompt.strip(), (
        f"kb/{ctx.language}/{expected_mode}/system.md resolved empty."
    )


def test_build_prompt_context_unmapped_intent_defers_to_route_table_default() -> None:
    """An unmapped intent falls back to mode="" — route-table default routing.

    The fallback is the empty context mode, so ``resolve_prompt_route``
    defers to the intent's governed ``default_mode`` (single source of
    truth) instead of hardcoding a mode at the app layer.
    """
    ctx = build_prompt_context(LLMIntent.KB_IMPROVE, "character", {})

    assert ctx.mode == ""

    route = resolve_prompt_route(LLMIntent.KB_IMPROVE, ctx.mode)
    assert route.mode == "improve"
