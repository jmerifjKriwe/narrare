"""Render-level tests for the remap composed prompt (R2 Batch D, pure-D).

Before R2 Batch D (2026-09-12): the remap template's rogue level-2 headers
(## Output Format L15, ## Do NOT L31) truncated the System Prompt at parse
time (extract_section boundary) — only the intro (structure_type/summary
demands) rendered; the Output-Format contract, Edge Cases, Do-NOT list,
Constraints, and User Preferences sections never rendered.

R2 Batch D is a PURE-D DEMOTION (no deletions, no supply changes): the
dropped region L15-43 carries exactly two new placeholder demands —
``{{avoidance_patterns}}`` (L39) and ``{{user_preferences}}`` (L43) — both
already satisfied on the governed EXTRACT route: ``avoidance_patterns`` is
declared optional (route_table LLMIntent.EXTRACT), ``user_preferences`` is
a PromptContext dataclass field (always present). The pre-existing
``{{structure_type}}`` / ``{{summary}}`` demands (L11/L13, above the old
cutoff) are unchanged and supplied route-exactly per the remap
ManualInjectionDeclaration (``variables=("summary", "structure_type")`` in
``packages/core/narrare_core/planning/remap.py``).

* ``## Output Format`` → ``### Output Format`` (L3 children become siblings)
* ``## Do NOT`` → ``### Do NOT``
* prompt_version 1.0.1 → 1.1.0

EXTRACT-route enriched behavior (SPECIAL): compose is asserted non-crashing
with BOTH empty and enriched ``avoidance_patterns`` / ``user_preferences``.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive Do-NOT content from the restored tail (dropped L31-35 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT guess — if no stage fits closely, say so and explain why",
    "Do NOT return multiple stages — choose the single best match",
    "Do NOT rewrite or edit the content — analyze the structure only",
)

# Restored tail sections (dropped L15-43 pre-slice).
_RESTORED_TAIL_SECTIONS = (
    "### Output Format",
    "### Edge Cases",
    "### Do NOT",
    "### Constraints",
    "### User Preferences",
)

# Pre-existing demands above the old cutoff — unchanged by the demotion.
_ALREADY_LIVE_CONTENT = (
    "{{structure_type}}",
    "{{summary}}",
)


def _prompt_path():
    return bundled_prompts_root() / "analysis" / "en" / "remap" / "system.md"


def _route_context(
    avoidance_patterns: str = "",
    user_preferences: str = "",
) -> PromptContext:
    """Governed EXTRACT/remap route context: the template's data inputs
    (``structure_type`` / ``summary``) supplied per the remap
    ManualInjectionDeclaration; avoidance/preferences default empty and can
    be enriched by tests."""
    ctx = PromptContext(
        language="en",
        mode="remap",
        extra={
            "structure_type": "three-act",
            "summary": "The protagonist discovers the hidden map and commits to the journey.",
        },
    )
    if avoidance_patterns:
        ctx.extra["avoidance_patterns"] = avoidance_patterns
    if user_preferences:
        ctx.extra["user_preferences"] = user_preferences
    return ctx


async def _compose(ctx: PromptContext):
    """Compose the remap prompt via real registry + composer (EXTRACT route)."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.EXTRACT, ctx)


class TestRemapHeaderSurgery:
    """R2 Batch D (D): the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_section(self) -> None:
        """The registry-parsed System Prompt includes the demoted sections and
        the previously-truncated L3 sections — proof they survive the
        extract_section boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(category="analysis", language="en", mode="remap")
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        assert "### Output Format" in resolved.system_prompt, "demoted Output Format missing"
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in resolved.system_prompt, f"missing section {section!r}"

    def test_prompt_version_bumped_to_1_1_0(self) -> None:
        """Header surgery bumps the template minor version (1.0.1 → 1.1.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.1.0"

    def test_source_keeps_pre_existing_demands(self) -> None:
        """The demotion does not touch the pre-existing structure_type /
        summary placeholders above the old cutoff."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        for token in _ALREADY_LIVE_CONTENT:
            assert token in body, f"regression: {token!r} removed"


class TestRemapTailActivation:
    """The activation contract: the truncated tail now renders, nothing moved."""

    async def test_route_context_compose_succeeds_empty(self) -> None:
        """Governed-route context (empty avoidance_patterns /
        user_preferences) composes without PromptVariableError."""
        prompt = await _compose(_route_context())
        assert "story structure analyst" in prompt.system
        assert "### Do NOT" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt."""
        prompt = await _compose(_route_context())
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"

    async def test_enriched_context_compose_no_raise(self) -> None:
        """EXTRACT-route enriched behavior: populated avoidance_patterns /
        user_preferences compose cleanly and reach the render."""
        prompt = await _compose(
            _route_context(
                avoidance_patterns="- No cliffhangers",
                user_preferences="- Prefers active voice",
            )
        )
        assert "{{" not in prompt.system, "placeholder residue in render"
        assert "- No cliffhangers" in prompt.system
        assert "- Prefers active voice" in prompt.system
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in prompt.system, f"missing restored section {section!r}"
