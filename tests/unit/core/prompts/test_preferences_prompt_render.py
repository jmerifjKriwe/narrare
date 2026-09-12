"""Render-level tests for the preferences composed prompt (R2 Batch D, pure-D).

Before R2 Batch D (2026-09-12): the preferences template's rogue level-2
headers (## Output Format L30, ## Do NOT L83) truncated the System Prompt at
parse time (extract_section boundary) — the Structured Output schema,
Analysis Guidelines, Constraints, and Do-NOT list never rendered. Everything
above the cutoff (System Prompt intro / Context / User Preferences — all
level-3) already rendered live.

R2 Batch D is a PURE-D DEMOTION (no deletions, no supply changes): the
dropped region L30-88 carries exactly two new placeholder demands —
``{{writing_language}}`` (L77) and ``{{avoidance_patterns}}`` (L81) — both
already satisfied on the governed EXTRACT route: ``writing_language`` is a
PromptContext dataclass field (always present), ``avoidance_patterns`` is
declared optional (route_table LLMIntent.EXTRACT). Confirmed by probe (real
Registry+Composer, route-exact context mirroring the preference-analysis
seam ``apps/api/narrare/memory/_agent_runner.py``): compose no-raise, zero
``{{...}}`` residue, and the pre-change render is a byte-prefix of the
post-change render (pure tail activation, +2593 chars).

* ``## Output Format`` → ``### Output Format`` (L3 children become siblings)
* ``## Do NOT`` → ``### Do NOT``
* prompt_version 1.0.2 → 1.1.0

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

# Distinctive Do-NOT content from the restored tail (dropped L83-88 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT rewrite or edit the content — analyze, don't create",
    "Do NOT provide generic feedback without specific references",
    "Do NOT fabricate patterns — only report what you observe",
    "Do NOT judge or evaluate preferences — describe them neutrally",
)

# Restored Output-Format tail markers (dropped L30-81 pre-slice).
_RESTORED_TAIL_SECTIONS = (
    "### Output Format",
    "### Structured Output",
    "### Analysis Guidelines",
    "### Constraints",
)

# Sections that already rendered above the cutoff — must survive untouched.
_ALREADY_LIVE_SECTIONS = (
    "### Context",
    "### User Preferences",
)


def _prompt_path():
    return bundled_prompts_root() / "analysis" / "en" / "preferences" / "system.md"


def _route_context(
    avoidance_patterns: str = "",
    user_preferences: str = "",
) -> PromptContext:
    """Route-exact context mirroring the preference-analysis seam
    (``_agent_runner.py``: mode="preferences", ``event_count`` extra).
    ``avoidance_patterns`` / ``user_preferences`` start empty (production
    shape) and can be enriched by tests."""
    ctx = PromptContext(
        language="en",
        genre="",
        mode="preferences",
        extra={"event_count": "18"},
    )
    if avoidance_patterns:
        ctx.extra["avoidance_patterns"] = avoidance_patterns
    if user_preferences:
        ctx.extra["user_preferences"] = user_preferences
    return ctx


async def _compose(ctx: PromptContext):
    """Compose the preferences prompt via real registry + composer (EXTRACT route)."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.EXTRACT, ctx)


class TestPreferencesHeaderSurgery:
    """R2 Batch D (D): the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_section(self) -> None:
        """The registry-parsed System Prompt includes the demoted sections —
        proof they survive the extract_section boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(category="analysis", language="en", mode="preferences")
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        assert "### Output Format" in resolved.system_prompt, "demoted Output Format missing"
        for section in _ALREADY_LIVE_SECTIONS:
            assert section in resolved.system_prompt, f"regression: {section!r} dropped"

    def test_prompt_version_bumped_to_1_1_0(self) -> None:
        """Header surgery bumps the template minor version (1.0.2 → 1.1.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.1.0"


class TestPreferencesTailActivation:
    """The activation contract: the truncated tail now renders, nothing moved."""

    async def test_route_context_compose_succeeds_empty(self) -> None:
        """Production-shape context (empty avoidance_patterns /
        user_preferences) composes without PromptVariableError."""
        prompt = await _compose(_route_context())
        assert "writing preference analyst" in prompt.system
        assert "### Do NOT" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt."""
        prompt = await _compose(_route_context())
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"

    async def test_composed_system_contains_restored_output_format(self) -> None:
        """The restored Output-Format tail (schema fields, guidelines,
        constraints) reaches the composed system prompt."""
        prompt = await _compose(_route_context())
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in prompt.system, f"missing restored section {section!r}"
        assert "**avoidance_patterns**" in prompt.system

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
