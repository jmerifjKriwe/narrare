"""Render-level tests for the character_voice composed prompt (R2 Batch A, pure-D).

Before R2 Batch A (2026-09-12): the character_voice template's rogue level-2
header (## Do NOT L94) truncated the System Prompt at parse time
(extract_section boundary) — the Do-NOT list never rendered. Everything
above the cutoff (Your Task / Context / Known Characters and World Context /
User Preferences / Constraints / Output Format / Quality Rules — all level-3)
already rendered live.

R2 Batch A is a PURE-D DEMOTION (no deletions, no supply changes): the dropped
region carries zero ``{{placeholders}}`` (triage-verified), so demotion alone
activates it with zero new variable demands — confirmed by probe (real
Registry+Composer, route-exact context mirroring
``apps/api/narrare/analysis/character_voice_prompt.py``): compose no-raise,
zero ``{{...}}`` residue, and the pre-change render is a byte-prefix of the
post-change render (pure tail activation, +515 chars).

* ``## Do NOT`` → ``### Do NOT`` (no child headers to shift — list items only)
* prompt_version 1.0.0 → 1.1.0

Unlike beta_reader/deepdive (D+X) no registry entries were pruned, and unlike
summarize no supply wiring was needed: the kb_* / metadata placeholders were
already live above the cutoff — the VOICE route declares them optional
(RULE-11); ``resolve_character_voice_prompt`` declares the kb_* slots
explicitly (``kb_relationships`` from the caller, the rest empty).
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive Do-NOT content from the restored tail (dropped L94-100 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT recompute or fabricate the deterministic metrics",
    "Do NOT persist `distinctiveness_notes` as if it were an intrinsic",
)

# Sections that already rendered above the cutoff — must survive untouched.
_ALREADY_LIVE_SECTIONS = (
    "### Your Task",
    "### Context",
    "### Known Characters and World Context",
    "### User Preferences",
    "### Constraints",
    "### Output Format",
    "### Quality Rules",
)


def _prompt_path():
    return bundled_prompts_root() / "analysis" / "en" / "character_voice" / "system.md"


def _route_context(kb_relationships: str = "") -> PromptContext:
    """Route-exact context mirroring resolve_character_voice_prompt
    (``kb_relationships`` comes from the caller — populated variant probed
    alongside the empty one)."""
    return PromptContext(
        language="en",
        writing_language="en",
        project_title="The Thornwall Echoes",
        genre="Fantasy",
        mode="character_voice",
        extra={
            "kb_characters": "",
            "kb_locations": "",
            "kb_factions": "",
            "kb_relationships": kb_relationships,
        },
    )


async def _compose(ctx: PromptContext):
    """Compose the character_voice prompt via real registry + composer."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.VOICE, ctx)


class TestCharacterVoiceHeaderSurgery:
    """R2 Batch A (D): the source template has exactly one level-2 header."""

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
            category="analysis", language="en", mode="character_voice"
        )
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        for section in _ALREADY_LIVE_SECTIONS:
            assert section in resolved.system_prompt, f"regression: {section!r} dropped"

    def test_prompt_version_bumped_to_1_1_0(self) -> None:
        """Header surgery bumps the template minor version (1.0.0 → 1.1.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.1.0"


class TestCharacterVoiceDoNotActivation:
    """The activation contract: the Do-NOT tail now renders, nothing else moved."""

    async def test_route_context_compose_succeeds(self) -> None:
        """Route-exact context composes without PromptVariableError — zero new
        demands from the activated region (probe verdict as a pin)."""
        prompt = await _compose(_route_context())
        assert "character-voice profiling specialist" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt (populated kb_relationships included — the
        caller-supplied production shape)."""
        prompt = await _compose(_route_context(kb_relationships="- Elena <-> Mara: sisters"))
        assert "### Do NOT" in prompt.system
        assert "- Elena <-> Mara: sisters" in prompt.system
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"

    async def test_composed_system_carries_no_placeholder_residue(self) -> None:
        """rg-style containment: the render leaks no ``{{...}}`` token."""
        prompt = await _compose(_route_context())
        assert "{{" not in prompt.system, "placeholder residue in render"

    async def test_bare_context_compose_no_raise(self) -> None:
        """Bare context (no extra, no metadata) composes — every template
        variable is optional on the VOICE route (RULE-11)."""
        prompt = await _compose(
            PromptContext(language="en", mode="character_voice", project_title="")
        )
        assert "### Do NOT" in prompt.system
        assert "{{" not in prompt.system
