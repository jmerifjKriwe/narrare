"""Render-level tests for the dialogue_coach composed prompt (R2 Batch C, pure-D).

Before R2 Batch C (2026-09-12): the dialogue_coach template's rogue level-2
header (## Do NOT L112) truncated the System Prompt at parse time
(extract_section boundary) — the Do-NOT list (injection-defense + rewrite
discipline) never rendered. Everything above the cutoff (Your Task / Context /
Known Characters / Character Voice Profiles / User Preferences / Style
Constraints / Avoidance Patterns / Dialogue to Analyse / Constraints /
Output Format / Quality Rules — all level-3) already rendered live.

R2 Batch C is a PURE-D DEMOTION (no deletions, no supply changes): the dropped
region carries zero unresolved ``{{placeholders}}`` (its two
``{{character_voice_profiles}}`` / ``{{characters}}`` mentions are quoted
field semantics of already-live variables above the cutoff), so demotion alone
activates it with zero new variable demands — confirmed by probe (real
Registry+Composer, route-exact context mirroring
``apps/api/narrare/ai_assist/_prompt.py``): compose no-raise, zero ``{{...}}``
residue, and the pre-change render is a byte-prefix of the post-change render
(pure tail activation, +763 chars).

* ``## Do NOT`` → ``### Do NOT`` (no child headers to shift — list items only)
* prompt_version 1.0.0 → 1.1.0
* ``tests/unit/core/prompts/test_dialogue_coach_template.py`` raw-header pin
  updated in the same slice (``"## Do NOT"`` → ``"### Do NOT"``).
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive Do-NOT content from the restored tail (dropped L112-121 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT reference or rely on any numeric per-character statistics",
    "Do NOT rewrite dialogue in `analyze` mode",
    "Do NOT skip the `adaptive_summary` field",
)

# Sections that already rendered above the cutoff — must survive untouched.
_ALREADY_LIVE_SECTIONS = (
    "### Your Task",
    "### Context",
    "### Known Characters (canonical speaker roster)",
    "### Character Voice Profiles (descriptive — match dialogue against these)",
    "### User Preferences",
    "### Style Constraints",
    "### Avoidance Patterns",
    "### Dialogue to Analyse",
    "### Constraints",
    "### Output Format",
    "### Quality Rules",
)


def _prompt_path():
    return bundled_prompts_root() / "ai_assist" / "en" / "dialogue_coach" / "system.md"


def _route_context() -> PromptContext:
    """Route-exact context mirroring resolve_dialogue_coach_prompt.

    ``adaptive_extra`` is empty as it is when no enricher populates it —
    the four adaptive variables are optional on the DIALOGUE_COACH route.
    """
    return PromptContext(
        language="en",
        writing_language="en",
        project_title="The Thornwall Echoes",
        genre="Fantasy",
        mode="dialogue_coach",
        extra={
            "mode": "analyze",
            "characters": "Mira, Thorn",
            "text_to_analyze": '"You came back," Mira said.',
        },
    )


async def _compose(ctx: PromptContext):
    """Compose the dialogue_coach prompt via real registry + composer."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.DIALOGUE_COACH, ctx)


class TestDialogueCoachHeaderSurgery:
    """R2 Batch C (D): the source template has exactly one level-2 header."""

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
            category="ai_assist", language="en", mode="dialogue_coach"
        )
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        for section in _ALREADY_LIVE_SECTIONS:
            assert section in resolved.system_prompt, f"regression: {section!r} dropped"

    def test_prompt_version_bumped_to_1_1_0(self) -> None:
        """Header surgery bumps the template minor version (1.0.0 → 1.1.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.1.0"


class TestDialogueCoachDoNotActivation:
    """The activation contract: the Do-NOT tail now renders, nothing else moved."""

    async def test_route_context_compose_succeeds(self) -> None:
        """Route-exact context composes without PromptVariableError — zero new
        demands from the activated region (probe verdict as a pin)."""
        prompt = await _compose(_route_context())
        assert "dialogue coaching specialist" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt."""
        prompt = await _compose(_route_context())
        assert "### Do NOT" in prompt.system
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"

    async def test_composed_system_carries_no_placeholder_residue(self) -> None:
        """rg-style containment: the render leaks no ``{{...}}`` token."""
        prompt = await _compose(_route_context())
        assert "{{" not in prompt.system, "placeholder residue in render"

    async def test_bare_context_compose_no_raise(self) -> None:
        """Bare context (no extra, no metadata) composes — every template
        variable is optional on the DIALOGUE_COACH route (RULE-11)."""
        prompt = await _compose(
            PromptContext(language="en", mode="dialogue_coach", project_title="")
        )
        assert "### Do NOT" in prompt.system
        assert "{{" not in prompt.system
