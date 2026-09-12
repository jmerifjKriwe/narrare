"""Render-level tests for the outline composed prompt (R2 Batch F, pure-D).

Before R2 Batch F (2026-09-12): the outline template's rogue level-2 headers
(## Output Format L36, ## Do NOT L62) truncated the System Prompt at parse
time (extract_section boundary) — only the intro, Context, and Knowledge Base
sections rendered; the Output-Format contract, Outline Guidelines,
User Preferences, Do-NOT list, and Constraints sections never rendered.

R2 Batch F is a PURE-D DEMOTION (no deletions, no supply changes): the
dropped region L36-74 carries exactly two new placeholder demands —
``{{user_preferences}}`` (L60) and ``{{avoidance_patterns}}`` (L74) — both
PromptContext dataclass fields (always present via ``as_variables()``), so
they render empty by default on the governed PLAN route. The pre-existing
``{{variant_count}}`` / ``{{kb_characters}}`` / ``{{kb_locations}}`` demands
(L26/L31/L34, above the old cutoff) are unchanged and supplied via context
``extra`` exactly as the template already required before this slice.

* ``## Output Format`` → ``### Output Format`` (L3 children stay siblings)
* ``## Do NOT`` → ``### Do NOT``
* prompt_version 1.0.1 → 1.1.0

PLAN-route probe verdict (real registry + composer, mode="outline"):
+1816 chars, byte-prefix property holds, empty AND enriched
``avoidance_patterns`` / ``user_preferences`` compose non-crashing.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive Do-NOT content from the restored tail (dropped L62-67 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT introduce characters or locations not in the Knowledge Base without noting them as new",
    "Do NOT resolve major plot arcs in a single chapter unless requested",
    "Do NOT add filler scenes that don't advance the story",
    "Do NOT ignore genre conventions",
)

# Restored tail sections (dropped L36-74 pre-slice). Children stay L3 siblings.
_RESTORED_TAIL_SECTIONS = (
    "### Output Format",
    "### Structured Output",
    "### Outline Guidelines",
    "### User Preferences",
    "### Do NOT",
    "### Constraints",
)

# Pre-existing demands above the old cutoff — unchanged by the demotion.
_ALREADY_LIVE_CONTENT = (
    "{{variant_count}}",
    "{{kb_characters}}",
    "{{kb_locations}}",
)


def _prompt_path():
    return bundled_prompts_root() / "planning" / "en" / "outline" / "system.md"


def _route_context(
    avoidance_patterns: str = "",
    user_preferences: str = "",
) -> PromptContext:
    """Governed PLAN/outline route context: base fields as supplied by the
    WritingGraph ``get_outline_prompt`` seam; the template's pre-existing
    ``variant_count`` / ``kb_characters`` / ``kb_locations`` demands supplied
    via ``extra``; avoidance/preferences default empty (dataclass fields) and
    can be enriched by tests."""
    ctx = PromptContext(
        language="en",
        writing_language="en",
        genre="Fantasy",
        tone="epic",
        project_title="",
        mode="outline",
        extra={
            "variant_count": 1,
            "kb_characters": "### Character: Alice\nProtagonist",
            "kb_locations": "### Location: Castle\nMain setting",
        },
    )
    if avoidance_patterns:
        ctx.extra["avoidance_patterns"] = avoidance_patterns
    if user_preferences:
        ctx.extra["user_preferences"] = user_preferences
    return ctx


async def _compose(ctx: PromptContext):
    """Compose the outline prompt via real registry + composer (PLAN route)."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.PLAN, ctx)


class TestOutlineHeaderSurgery:
    """R2 Batch F: the source template has exactly one level-2 header."""

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
        resolved = await registry.resolve(category="planning", language="en", mode="outline")
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        assert "### Output Format" in resolved.system_prompt, "demoted Output Format missing"
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in resolved.system_prompt, f"missing section {section!r}"

    def test_prompt_version_bumped_to_1_1_0(self) -> None:
        """Header surgery bumps the template minor version (1.0.1 → 1.1.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.1.0"

    def test_source_keeps_pre_existing_demands(self) -> None:
        """The demotion does not touch the pre-existing variant_count / KB
        placeholders above the old cutoff."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        for token in _ALREADY_LIVE_CONTENT:
            assert token in body, f"regression: {token!r} removed"


class TestOutlineTailActivation:
    """The activation contract: the truncated tail now renders, nothing moved."""

    async def test_route_context_compose_succeeds_empty(self) -> None:
        """Governed-route context (empty avoidance_patterns /
        user_preferences) composes without PromptVariableError."""
        prompt = await _compose(_route_context())
        assert "story outlining specialist" in prompt.system
        assert "### Do NOT" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt."""
        prompt = await _compose(_route_context())
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"

    async def test_enriched_context_compose_no_raise(self) -> None:
        """PLAN-route enriched behavior: populated avoidance_patterns /
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
