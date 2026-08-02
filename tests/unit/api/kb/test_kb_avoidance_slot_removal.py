"""Prompt-composition tests for the avoidance_patterns slot removal (item 3).

The ``{{avoidance_patterns}}`` slot in the kb/merge and kb/extract templates
is a dead variable at runtime: the author's avoidance data already reaches the
LLM via ``user_preferences`` (the preferences enricher maps "what does the
user dislike or want to avoid?" into ``constraints`` → ``to_prompt_text()`` →
``user_preferences``). Per the honesty mandate the redundant slot is removed
from these two operations — but ``{{user_preferences}}`` (the live carrier) is
kept. These tests pin that contract: the templates must no longer reference
``avoidance_patterns``, must still reference ``user_preferences``, and must
substitute without raising ``PromptVariableError``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts import PromptComposer, PromptRegistry
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import PromptVariableError

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


def _read(mode: str) -> str:
    return (_BUNDLED / mode / "system.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def composer() -> PromptComposer:
    return PromptComposer(PromptRegistry())


# ---------------------------------------------------------------------------
# Template-level: avoidance removed, user_preferences kept
# ---------------------------------------------------------------------------


@pytest.mark.mutation_inert
def test_merge_template_drops_avoidance_keeps_user_preferences() -> None:
    """Static template assertion — mutations-invariant asset structure check.

    ``mutation_inert``: this asserts on the committed bundled template
    (``_bundled/kb/en/merge/system.md``) reached via ``parents[4]``. It cannot
    kill source-code mutants, and the asset path resolves to a non-existent
    location inside MutMut's ``mutants/`` sandbox (``parents[4]`` lands on
    ``<repo>/mutants``), crashing the mutation run (issue #146). MutMut's
    ``-m "not mutation_inert"`` filter excludes it — consistent with the
    reference asset tests. Enforced by
    scripts/checks/check_mutation_inert_assets.py. (The async composition
    tests below are NOT marked: they exercise real PromptComposer logic
    that mutations can legitimately kill.)
    """
    text = _read("merge")

    assert "{{avoidance_patterns}}" not in text, (
        "kb/merge must not declare the dead {{avoidance_patterns}} slot — "
        "avoidance data reaches the LLM via user_preferences."
    )
    assert "{{user_preferences}}" in text, (
        "kb/merge must keep {{user_preferences}} — it is the live carrier of "
        "avoidance/preference data and the mem0_preferences evidence var."
    )


@pytest.mark.mutation_inert
def test_extract_template_drops_avoidance_keeps_user_preferences() -> None:
    """Static template assertion — mutations-invariant asset structure check.

    ``mutation_inert``: same rationale as ``test_merge_template_...`` above.
    """
    text = _read("extract")

    assert "{{avoidance_patterns}}" not in text, (
        "kb/extract must not declare the dead {{avoidance_patterns}} slot."
    )
    assert "{{user_preferences}}" in text, "kb/extract must keep {{user_preferences}}."


# ---------------------------------------------------------------------------
# Composition: substitution resolves without PromptVariableError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_template_composes_without_avoidance(composer: PromptComposer) -> None:
    """A full merge context substitutes cleanly after the slot removal."""
    ctx = PromptContext(
        language="en",
        writing_language="en",
        project_title="My Epic",
        genre="Fantasy",
        entity_type="character",
        mode="merge",
        user_preferences="## Constraints\n- Avoid graphic violence",
        extra={
            "candidate_pairs": "Pair 1: Alice / Alis",
            "world_context": "- Alice (character): protagonist",
        },
    )

    composed = await composer.build(LLMIntent.KB_CONSISTENCY, ctx)

    # No dangling placeholder and no avoidance reference.
    assert "{{" not in composed.system
    assert "avoidance_patterns" not in composed.system
    # user_preferences is the live carrier — it must reach the prompt.
    assert "Avoid graphic violence" in composed.system


@pytest.mark.asyncio
async def test_extract_template_composes_without_avoidance(composer: PromptComposer) -> None:
    """A full extract context substitutes cleanly after the slot removal."""
    ctx = PromptContext(
        language="en",
        writing_language="en",
        mode="extract",
        chapter_title="Chapter 1",
        genre="Fantasy",
        user_preferences="## Constraints\n- Avoid cliffhangers",
        extra={
            "existing_entity_names": "Anna",
            "world_context": "- Anna (character): protagonist",
        },
    )

    composed = await composer.build(LLMIntent.KB_EXTRACT, ctx)

    assert "{{" not in composed.system
    assert "avoidance_patterns" not in composed.system
    assert "Avoid cliffhangers" in composed.system


def test_no_undeclared_reference_raises_prompt_variable_error() -> None:
    """Sanity: an undeclared variable reference WOULD raise — proving the
    composition tests above are meaningful (the engine is strict)."""
    from narrare_core.prompts.variable_engine import prepare_variables_for_template

    with pytest.raises(PromptVariableError):
        prepare_variables_for_template(
            "Hello {{totally_made_up_var_xyz}}",
            variables={},
        )
