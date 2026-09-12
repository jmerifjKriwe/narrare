"""Render-level tests for the review composed prompt (R2 Batch D, pure-D).

Before R2 Batch D (2026-09-12): the review template's rogue level-2 headers
(## Output Format L56, ## Do NOT L118) truncated the System Prompt at parse
time (extract_section boundary) — the Structured Output schema, Review
Guidelines, and Do-NOT list never rendered. Everything above the cutoff
(System Prompt intro / Context / Knowledge Base / User Preferences /
Constraints — all level-3) already rendered live.

R2 Batch D is a PURE-D DEMOTION (no deletions, no supply changes): the
dropped region L56-123 carries zero ``{{placeholders}}`` (triage-verified),
so demotion alone activates it with zero new variable demands — confirmed by
probe (real Registry+Composer, route-exact context mirroring the graph
review seam ``get_review_prompt`` in
``packages/core/narrare_core/agents/writing_graph_prompts.py``): compose
no-raise, zero ``{{...}}`` residue, and the pre-change render is a
byte-prefix of the post-change render (pure tail activation, +3675 chars).

* ``## Output Format`` → ``### Output Format`` (L3 children become siblings)
* ``## Do NOT`` → ``### Do NOT``
* prompt_version 1.3.1 → 1.4.0

The governed composer route for analysis/review is ``LLMIntent.ANALYSE``
(route_table default mode ``review``).
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive Do-NOT content from the restored tail (dropped L118-123 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT rewrite the draft — provide guidance for the author to revise",
    "Do NOT introduce new plot elements or characters not in the draft",
    "Do NOT provide generic feedback without specific references",
    "Do NOT suggest changes to the author's stated preferences",
)

# Restored Output-Format tail markers (dropped L56-106 pre-slice).
_RESTORED_TAIL_SECTIONS = (
    "### Output Format",
    "### Structured Output",
    "### Review Guidelines",
)

# Sections that already rendered above the cutoff — must survive untouched.
_ALREADY_LIVE_SECTIONS = (
    "### Context",
    "### Knowledge Base",
    "### User Preferences",
    "### Constraints",
)


def _prompt_path():
    return bundled_prompts_root() / "analysis" / "en" / "review" / "system.md"


def _route_context(kb_relationships: str = "") -> PromptContext:
    """Route-exact context mirroring get_review_prompt enrichment:
    word_target/word_count extras, user_preferences, and the ten KB
    extras from ``kb_context_extras`` (populated variant probed via
    ``kb_relationships`` — the caller-supplied production shape)."""
    ctx = PromptContext(
        language="en",
        writing_language="en",
        genre="Fantasy",
        tone="",
        project_title="The Thornwall Echoes",
        chapter_title="Chapter 1",
    )
    ctx.mode = "review"
    ctx.extra = {
        "word_target": "2000",
        "word_count": "1800",
        "user_preferences": "- Prefers concise sentences",
        "kb_characters": "",
        "kb_locations": "",
        "kb_factions": "",
        "kb_other": "",
        "kb_relationships": kb_relationships,
        "kb_suggested": "",
        "kb_systems": "",
        "kb_timelines": "",
        "kb_pinned": "",
        "kb_context_warnings": "",
    }
    return ctx


async def _compose(ctx: PromptContext):
    """Compose the review prompt via real registry + composer (ANALYSE route)."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.ANALYSE, ctx)


class TestReviewHeaderSurgery:
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
        resolved = await registry.resolve(category="analysis", language="en", mode="review")
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        assert "### Output Format" in resolved.system_prompt, "demoted Output Format missing"
        for section in _ALREADY_LIVE_SECTIONS:
            assert section in resolved.system_prompt, f"regression: {section!r} dropped"

    def test_prompt_version_bumped_to_1_4_0(self) -> None:
        """Header surgery bumps the template minor version (1.3.1 → 1.4.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.4.0"


class TestReviewTailActivation:
    """The activation contract: the truncated tail now renders, nothing moved."""

    async def test_route_context_compose_succeeds(self) -> None:
        """Route-exact context composes without PromptVariableError — zero new
        demands from the activated region (probe verdict as a pin)."""
        prompt = await _compose(_route_context())
        assert "professional writing critic and editor" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt (populated kb_relationships included — the
        caller-supplied production shape)."""
        prompt = await _compose(_route_context(kb_relationships="- Elena <-> Mara: sisters"))
        assert "### Do NOT" in prompt.system
        assert "- Elena <-> Mara: sisters" in prompt.system
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"

    async def test_composed_system_contains_restored_output_format(self) -> None:
        """The restored Output-Format tail (schema fields, guidelines) reaches
        the composed system prompt."""
        prompt = await _compose(_route_context())
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in prompt.system, f"missing restored section {section!r}"
        assert "**quality_score**" in prompt.system

    async def test_composed_system_carries_no_placeholder_residue(self) -> None:
        """rg-style containment: the render leaks no ``{{...}}`` token."""
        prompt = await _compose(_route_context())
        assert "{{" not in prompt.system, "placeholder residue in render"
