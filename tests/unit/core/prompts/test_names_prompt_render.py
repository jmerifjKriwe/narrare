"""Render-level tests for the names composed prompt (R2 Batch E, pure-D).

Before R2 Batch E (2026-09-12): the names template's rogue level-2 header
(## Do NOT L26) truncated the System Prompt at parse time (extract_section
boundary) — only the intro, culture guidelines, Task, and Parameters
sections rendered; the Do-NOT list, Output-Format contract, User
Preferences, Constraints, and Rules sections never rendered.

R2 Batch E is a PURE-D DEMOTION (no deletions, no supply changes): the
dropped region L26-57 carries exactly two new placeholder demands —
``{{user_preferences}}`` (L44) and ``{{avoidance_patterns}}`` (L49) — both
PromptContext dataclass fields (always present, default "").
``{{explanation_language}}`` (restored occurrence L48) was already a live
demand above the old cutoff (L23) and is supplied route-exactly via the
service extra (``apps/api/narrare/generation/name_service.py`` L148).

* ``## Do NOT`` → ``### Do NOT`` (L3 siblings)
* prompt_version 1.1.0 → 1.2.0

SPECIAL (Batch E): compose is asserted with ``explanation_language``
rendering populated from the service extra (not "").
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive Do-NOT content from the restored tail (dropped L26-31 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT generate names that already exist in the project",
    "Do NOT return more or fewer names than requested",
    "Do NOT add meta-commentary or explanations beyond what's requested",
)

# Restored tail sections (dropped L26-57 pre-slice).
_RESTORED_TAIL_SECTIONS = (
    "### Do NOT",
    "### Output Format",
    "### User Preferences",
    "### Constraints",
    "### Rules",
)

# Pre-existing demands above the old cutoff — unchanged by the demotion.
_ALREADY_LIVE_CONTENT = (
    "{{culture_guidelines}}",
    "{{explanation_language}}",
    "{{existing_names}}",
)


def _prompt_path():
    return bundled_prompts_root() / "generation" / "en" / "names" / "system.md"


def _route_context(
    explanation_language: str = "en",
    user_preferences: str = "",
    avoidance_patterns: str = "",
) -> PromptContext:
    """Governed NAME_GENERATE route context, mirroring the service seam
    (``apps/api/narrare/generation/name_service.py`` L139-150): language is
    the explanation language and every template data input arrives via
    ``extra``; user preferences / avoidance patterns default to the
    PromptContext dataclass values (""), enrichable by tests."""
    ctx = PromptContext(
        language=explanation_language,
        mode="names",
        user_preferences=user_preferences,
        avoidance_patterns=avoidance_patterns,
        extra={
            "name_style": "fantasy",
            "name_type": "character",
            "count": "5",
            "gender": "female",
            "existing_names": "Elara, Thorne",
            "explanation_language": explanation_language,
        },
    )
    return ctx


async def _compose(ctx: PromptContext):
    """Compose the names prompt via real registry + composer (NAME_GENERATE)."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.NAME_GENERATE, ctx)


class TestNamesHeaderSurgery:
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
        resolved = await registry.resolve(category="generation", language="en", mode="names")
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in resolved.system_prompt, f"missing section {section!r}"

    def test_prompt_version_bumped_to_1_2_0(self) -> None:
        """Header surgery bumps the template minor version (1.1.0 → 1.2.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.2.0"

    def test_source_keeps_pre_existing_demands(self) -> None:
        """The demotion does not touch the pre-existing demands above the
        old cutoff."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        for token in _ALREADY_LIVE_CONTENT:
            assert token in body, f"regression: {token!r} removed"


class TestNamesTailActivation:
    """The activation contract: the truncated tail now renders, nothing moved."""

    async def test_route_context_compose_succeeds_empty(self) -> None:
        """Governed-route context (default "" dataclass preferences) composes
        without PromptVariableError."""
        prompt = await _compose(_route_context())
        assert "name generator" in prompt.system
        assert "### Do NOT" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header and its distinctive bullets reach the
        composed system prompt."""
        prompt = await _compose(_route_context())
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"
        for section in _RESTORED_TAIL_SECTIONS:
            assert section in prompt.system, f"missing restored section {section!r}"

    async def test_explanation_language_renders_populated_from_service_extra(self) -> None:
        """SPECIAL (Batch E): ``explanation_language`` supplied via the
        service extra renders populated (both Parameters and Constraints
        occurrences), and enriched dataclass preferences reach the render."""
        prompt = await _compose(
            _route_context(
                explanation_language="German",
                user_preferences="- Prefers mythological names",
                avoidance_patterns="- No modern English first names",
            )
        )
        assert "{{" not in prompt.system, "placeholder residue in render"
        assert "Explain meanings in: German" in prompt.system
        assert "Explain meanings in German" in prompt.system
        assert "- Prefers mythological names" in prompt.system
        assert "- No modern English first names" in prompt.system
