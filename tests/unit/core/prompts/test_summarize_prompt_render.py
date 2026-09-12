"""Render-level tests for the summarize composed prompt (R2 Slice 4, D-only).

Before R2 Slice 4 (2026-09-12): the summarize template's rogue level-2
headers (## Output Format L19, ## Do NOT L68) truncated the System Prompt at
parse time (extract_section boundary) — the live system prompt was the intro
plus task paragraph only; the output contract, Context / Knowledge Base /
User Preferences / Constraints sections, and the Do-NOT list never rendered.

R2 Slice 4 is a D-ONLY demotion (no deletions — unlike Slices 1/2 the supply
is LIVE): Slice 3 (2026-09-12) wired ``ChapterSummaryService`` to the
canonical ``KBContextProvider`` (ADR-067), spreading kb_characters /
kb_locations / kb_factions / kb_relationships into ``PromptContext.extra``
— provably render-inert while the placeholders sat below the parse cutoff
(``tests/unit/api/writing/test_summary_kb_inertness.py``). Every other
activated placeholder (project_title / genre / writing_language /
chapter_title / user_preferences / avoidance_patterns) is a ``PromptContext``
field; ``culture_guidelines`` was already active above the cutoff. Demotion
alone therefore activates the full template with zero supply changes:

* ``## Output Format`` → ``### Output Format`` (children ``### Context`` /
  ``### Knowledge Base`` / ``### User Preferences`` / ``### Constraints``
  shift to level-4, per the Slice 1/2 precedent)
* ``## Do NOT`` → ``### Do NOT``
* prompt_version 1.3.0 → 1.4.0

The empty-KB render keeps the per-slot labels ("Characters:" etc.) with blank
bodies — the same scaffolding convention as the activated coreference
template — with zero ``{{...}}`` residue (RULE-11 graceful degradation).
Byte-exact goldens live in ``test_summarize_goldens.py`` (shared SSOT with the
service-seam test, RULE-04).
"""

from __future__ import annotations

from dataclasses import fields

from narrare.kb.context_contracts import KBContextBundle
from narrare_core.context._kb_envelope import RenderedKBContext
from narrare_core.context._render_options import RenderOptions
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.variable_registry import SYSTEM_VARS
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root
from tests.unit.core.prompts.test_summarize_goldens import (
    GOLDEN_SYSTEM_EMPTY_KB,
    GOLDEN_SYSTEM_POPULATED,
)

_KB_SENTINELS = (
    "- Alice (character): the protagonist",
    "- Berlin (location): where the story happens",
    "- The Cult (faction): antagonists",
    "- Alice <-> Bob: rivals",
)

_PREF_SENTINEL = "PREF: prefers concise summaries without spoilers."
_AVOID_SENTINEL = "AVOID: no dream sequences."


def _prompt_path():
    return bundled_prompts_root() / "analysis" / "en" / "summarize" / "system.md"


def _rendered(text: str) -> RenderedKBContext:
    """Build a RenderedKBContext for tests (provenance not asserted here)."""
    return RenderedKBContext(
        text=text,
        preserved_fields=frozenset(),
        omitted_fields=(),
        entry_count=1,
        render_path="test._rendered",
    )


def _bundle_with_data() -> KBContextBundle:
    """A bundle whose four slots carry non-empty rendered KB context."""
    return KBContextBundle(
        characters=_rendered("- Alice (character): the protagonist"),
        locations=_rendered("- Berlin (location): where the story happens"),
        factions=_rendered("- The Cult (faction): antagonists"),
        relationships=_rendered("- Alice <-> Bob: rivals"),
        render_options=RenderOptions(annotate_provenance=True),
    )


def _empty_kb_vars() -> dict[str, str]:
    """The empty-bundle degradation supply (RULE-11)."""
    return KBContextBundle.empty(RenderOptions(annotate_provenance=True)).to_prompt_variables()


def _service_context(kb_vars: dict[str, str]) -> PromptContext:
    """The exact PromptContext shape summary_service.py builds (Slice 3)."""
    return PromptContext(
        language="en",
        genre="",
        chapter_title="Chapter 1",
        mode="summarize",
        extra={"max_sentences": "4", **kb_vars},
    )


async def _compose(kb_vars: dict[str, str]):
    """Compose the summarize prompt via real registry + composer."""
    return await PromptComposer(PromptRegistry()).build(
        LLMIntent.SUMMARIZE, _service_context(kb_vars)
    )


class TestSummarizeHeaderSurgery:
    """R2 Slice 4 (D): the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_sections(self) -> None:
        """The registry-parsed System Prompt includes the restored sections —
        proof they survive the extract_section boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(category="analysis", language="en", mode="summarize")
        for section in (
            "### Output Format",
            "#### Context",
            "#### Knowledge Base",
            "#### User Preferences",
            "#### Constraints",
            "### Do NOT",
        ):
            assert section in resolved.system_prompt, f"missing {section!r}"

    def test_prompt_version_bumped_to_1_4_0(self) -> None:
        """Header surgery bumps the template minor version (1.3.0 → 1.4.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.4.0"


class TestSummarizeActivatedRender:
    """The activation contract: the Slice-3 supply now reaches the render."""

    async def test_provider_data_render_matches_activation_golden(self) -> None:
        """Populated-KB render is byte-identical to the Slice 4 golden."""
        prompt = await _compose(_bundle_with_data().to_prompt_variables())
        assert prompt.system == GOLDEN_SYSTEM_POPULATED

    async def test_provider_data_renders_kb_blocks_and_craft_sections(self) -> None:
        """KB blocks render the provider's per-slot text; the restored craft
        sections reach the composed system prompt."""
        prompt = await _compose(_bundle_with_data().to_prompt_variables())
        for sentinel in _KB_SENTINELS:
            assert sentinel in prompt.system, f"missing kb sentinel {sentinel!r}"
        for fragment in (
            "### Output Format",
            "Return a JSON object:",
            "#### Context",
            "- Chapter: Chapter 1",
            "- Language: en",
            "#### Constraints",
            "Respect the author's avoidance patterns:",
            "### Do NOT",
            "Do NOT split the summary into bullet points",
        ):
            assert fragment in prompt.system, f"missing {fragment!r}"

    async def test_empty_bundle_render_matches_activation_empty_golden(self) -> None:
        """Empty-KB degradation renders every section empty-bodied (labels
        kept as scaffolding, coreference convention) — no graceful-degradation
        crash, byte-identical to the empty golden."""
        prompt = await _compose(_empty_kb_vars())
        assert prompt.system == GOLDEN_SYSTEM_EMPTY_KB

    async def test_renders_carry_no_placeholder_residue(self) -> None:
        """rg-style containment: neither render leaks a ``{{...}}`` token —
        every activated placeholder resolved (Slice 4 supply check)."""
        for kb_vars in (
            _bundle_with_data().to_prompt_variables(),
            _empty_kb_vars(),
        ):
            prompt = await _compose(kb_vars)
            assert "{{" not in prompt.system, "placeholder residue in render"

    async def test_empty_bundle_render_omits_kb_sentinels(self) -> None:
        """The empty-bundle render carries no populated-KB text."""
        prompt = await _compose(_empty_kb_vars())
        for sentinel in _KB_SENTINELS:
            assert sentinel not in prompt.system

    async def test_adaptive_fields_render_with_values(self) -> None:
        """user_preferences / avoidance_patterns render their adaptive
        values; writing_language falls back to the context language."""
        context = _service_context(_empty_kb_vars())
        context.user_preferences = _PREF_SENTINEL
        context.avoidance_patterns = _AVOID_SENTINEL
        prompt = await PromptComposer(PromptRegistry()).build(LLMIntent.SUMMARIZE, context)
        assert _PREF_SENTINEL in prompt.system
        assert _AVOID_SENTINEL in prompt.system
        assert "- Write in en" in prompt.system


class TestSummarizeSupplyContract:
    """Why D-only sufficed: every activated placeholder has live supply."""

    def test_activated_kb_vars_stay_registered(self) -> None:
        """The four kb_* slots remain governed SYSTEM_VARS (no prune here —
        unlike Slices 1/2 the blocks are live, not dead)."""
        for var in (
            "kb_characters",
            "kb_locations",
            "kb_factions",
            "kb_relationships",
        ):
            assert var in SYSTEM_VARS, f"{var} must remain registered"

    def test_activated_non_kb_vars_are_prompt_context_fields(self) -> None:
        """Every non-kb activated placeholder is a PromptContext field —
        the probe verdict encoded as a pin (kb_* come via the Slice-3
        provider spread, culture_guidelines via the composer seam)."""
        field_names = {f.name for f in fields(PromptContext)}
        for var in (
            "project_title",
            "genre",
            "writing_language",
            "chapter_title",
            "user_preferences",
            "avoidance_patterns",
        ):
            assert var in field_names, f"{var} is not a PromptContext field"
