"""Render-level tests for the series_consistency composed prompt (R2 Batch B, pure-D).

Before R2 Batch B (2026-09-12): the series_consistency template's rogue
level-2 header (## Do NOT L117) truncated the System Prompt at parse time
(extract_section boundary) — the Do-NOT list never rendered. Everything
above the cutoff (Your Task / Input / Context / Knowledge Base / Output
Format / Quality Rules / User Preferences / Constraints — all level-3)
already rendered live.

R2 Batch B is a PURE-D DEMOTION (no deletions, no supply changes): the dropped
region carries zero ``{{placeholders}}`` (triage-verified), so demotion alone
activates it with zero new variable demands — confirmed by probe (real
Registry+Composer, route-exact context mirroring
``apps/api/narrare/series/series_consistency_prompt.py``): compose no-raise,
zero ``{{...}}`` residue, and the pre-change render is a byte-prefix of the
post-change render (pure tail activation, +680 chars).

* ``## Do NOT`` → ``### Do NOT`` (no child headers to shift — list items only)
* prompt_version 1.0.0 → 1.1.0

No supply wiring was needed: the kb_* placeholders were already live above
the cutoff, declared explicitly (empty) by the seam — the authoritative
cross-novel facts are the Canon entries supplied at runtime as user input
(RULE-02a category 3), not the per-novel KB context variables.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive Do-NOT content from the restored tail (dropped L117-124 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT invent Canon entries",
    "Do NOT rewrite the chapter text or suggest edits — analysis only.",
)

# Sections that already rendered above the cutoff — must survive untouched.
_ALREADY_LIVE_SECTIONS = (
    "### Your Task",
    "### Input",
    "### Context",
    "### Knowledge Base",
    "### Output Format",
    "### Quality Rules",
    "### User Preferences",
    "### Constraints",
)


def _prompt_path():
    return bundled_prompts_root() / "analysis" / "en" / "series_consistency" / "system.md"


def _route_context(kb_vars: dict[str, str]) -> PromptContext:
    """Route-exact context mirroring resolve_series_consistency_prompt
    (ANALYSE + context_mode="series_consistency"; the seam declares the four
    kb_* slots explicitly, empty in production)."""
    return PromptContext(
        language="en",
        writing_language="en",
        project_title="Band One",
        genre="Fantasy",
        mode="series_consistency",
        extra={**(kb_vars or {})},
    )


_POPULATED_KB = {
    "kb_characters": "- Elara: sorceress",
    "kb_locations": "- Aldric Keep: capital",
    "kb_factions": "- Silver Order: knightly order",
    "kb_relationships": "- Elara <-> Aldric: allies",
}

_SEAM_EMPTY_KB = dict.fromkeys(_POPULATED_KB, "")


async def _compose(ctx: PromptContext):
    """Compose the series_consistency prompt via real registry + composer."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.ANALYSE, ctx)


class TestSeriesConsistencyHeaderSurgery:
    """R2 Batch B (D): the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_section(self) -> None:
        """The registry-parsed System Prompt includes the demoted Do-NOT
        section — proof it survives the extract_section boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(
            category="analysis", language="en", mode="series_consistency"
        )
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        for section in _ALREADY_LIVE_SECTIONS:
            assert section in resolved.system_prompt, f"regression: {section!r} dropped"

    def test_prompt_version_bumped_to_1_1_0(self) -> None:
        """Header surgery bumps the template minor version (1.0.0 → 1.1.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.1.0"


class TestSeriesConsistencyDoNotActivation:
    """The activation contract: the Do-NOT tail now renders, nothing else moved."""

    async def test_route_context_compose_succeeds(self) -> None:
        """Route-exact context composes without PromptVariableError — zero new
        demands from the activated region (probe verdict as a pin)."""
        prompt = await _compose(_route_context(_SEAM_EMPTY_KB))
        assert "cross-novel consistency checker" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt (populated per-novel KB context included —
        the interpretive-aid shape the template describes)."""
        prompt = await _compose(_route_context(_POPULATED_KB))
        assert "### Do NOT" in prompt.system
        assert "- Elara <-> Aldric: allies" in prompt.system
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"

    async def test_composed_system_carries_no_placeholder_residue(self) -> None:
        """rg-style containment: the render leaks no ``{{...}}`` token."""
        prompt = await _compose(_route_context(_SEAM_EMPTY_KB))
        assert "{{" not in prompt.system, "placeholder residue in render"

    async def test_seam_exact_empty_kb_compose_no_raise(self) -> None:
        """The seam-exact production shape (all four kb_* slots ``""`` — Canon
        entries flow as user-channel runtime data) still composes with the
        activated tail rendered."""
        prompt = await _compose(_route_context(_SEAM_EMPTY_KB))
        assert "### Do NOT" in prompt.system
        assert "{{" not in prompt.system
