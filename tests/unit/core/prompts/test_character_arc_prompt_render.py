"""Render-level tests for the character_arc composed prompt (R2 Batch E, pure-D).

Before R2 Batch E (2026-09-12): the character_arc template's rogue level-2
header (## Do NOT L80) truncated the System Prompt at parse time
(extract_section boundary) — everything through the Output-Format notes
rendered; the Do-NOT list, User Preferences, and Constraints sections
never rendered.

R2 Batch E is a PURE-D DEMOTION (no deletions, no supply changes): the
dropped region L80-96 carries exactly two new placeholder demands —
``{{user_preferences}}`` (L90) and ``{{avoidance_patterns}}`` (L95) — both
PromptContext dataclass fields (always present, default ""). All template
data inputs (``{{character_name}}``, ``{{character_current_state}}``,
``{{character_goal_state}}``, ``{{existing_plot_points}}``) sit above the
old cutoff and are supplied route-exactly via the service extra
(``apps/api/narrare/planning/character_arc_service.py`` L154-159).

* ``## Do NOT`` → ``### Do NOT`` (L3 siblings)
* prompt_version 1.0.0 → 1.1.0
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive Do-NOT content from the restored tail (dropped L82-86 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT invent a `flat` arc unless the genre or an explicit request demands it",
    "Do NOT skip the internal conflict",
    "Do NOT contradict the existing plot points",
    "Do NOT produce phases with no causal connection",
)

# Restored tail sections (dropped L80-96 pre-slice).
_RESTORED_TAIL_SECTIONS = (
    "### Do NOT",
    "### User Preferences",
    "### Constraints",
)

# Pre-existing demands above the old cutoff — unchanged by the demotion.
_ALREADY_LIVE_CONTENT = (
    "{{character_name}}",
    "{{character_current_state}}",
    "{{character_goal_state}}",
    "{{existing_plot_points}}",
)


def _prompt_path():
    return bundled_prompts_root() / "planning" / "en" / "character_arc" / "system.md"


def _route_context(
    user_preferences: str = "",
    avoidance_patterns: str = "",
) -> PromptContext:
    """Governed PLAN/character_arc route context, mirroring the service seam
    (``apps/api/narrare/planning/character_arc_service.py`` L148-160): all
    template data inputs arrive via ``extra``; user preferences / avoidance
    patterns default to the PromptContext dataclass values (""), enrichable
    by tests."""
    return PromptContext(
        language="en",
        writing_language="en",
        project_title="The Silent Meridian",
        genre="Fantasy",
        mode="character_arc",
        user_preferences=user_preferences,
        avoidance_patterns=avoidance_patterns,
        extra={
            "character_name": "Mira Voss",
            "character_current_state": "Distrusts her own judgement",
            "character_goal_state": "Leads with conviction",
            "existing_plot_points": "- Ch 3: Mira refuses the council seat",
        },
    )


async def _compose(ctx: PromptContext):
    """Compose via real registry + composer (PLAN route, character_arc mode)."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.PLAN, ctx)


class TestCharacterArcHeaderSurgery:
    """R2 Batch E (D): the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_section(self) -> None:
        """The registry-parsed System Prompt includes the demoted Do-NOT
        section and the previously-truncated tail — proof they survive the
        extract_section boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(category="planning", language="en", mode="character_arc")
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in resolved.system_prompt, f"missing section {section!r}"

    def test_prompt_version_bumped_to_1_1_0(self) -> None:
        """Header surgery bumps the template minor version (1.0.0 → 1.1.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.1.0"

    def test_source_keeps_pre_existing_demands(self) -> None:
        """The demotion does not touch the pre-existing demands above the
        old cutoff."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        for token in _ALREADY_LIVE_CONTENT:
            assert token in body, f"regression: {token!r} removed"


class TestCharacterArcTailActivation:
    """The activation contract: the truncated tail now renders, nothing moved."""

    async def test_route_context_compose_succeeds_empty(self) -> None:
        """Governed-route context (default "" dataclass preferences) composes
        without PromptVariableError."""
        prompt = await _compose(_route_context())
        assert "character development specialist" in prompt.system
        assert "### Do NOT" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt."""
        prompt = await _compose(_route_context())
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in prompt.system, f"missing restored section {section!r}"

    async def test_enriched_context_compose_no_raise(self) -> None:
        """Enriched dataclass preferences compose cleanly and reach the
        render with zero placeholder residue."""
        prompt = await _compose(
            _route_context(
                user_preferences="- Prefers understated turning points",
                avoidance_patterns="- No amnesia plots",
            )
        )
        assert "{{" not in prompt.system, "placeholder residue in render"
        assert "- Prefers understated turning points" in prompt.system
        assert "- No amnesia plots" in prompt.system
