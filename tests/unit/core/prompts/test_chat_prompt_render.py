"""Render-level tests for the chat composed prompt (R2 Batch C, pure-D).

Before R2 Batch C (2026-09-12): the chat template's rogue level-2 header
(## Do NOT L102) truncated the System Prompt at parse time (extract_section
boundary) — the Do-NOT list AND the Output Format tail never rendered.
Everything above the cutoff (Your Scope / Project Context / Style Profile /
Character Voice Profiles / Author Voice / Conversation History / Guidelines /
User Preferences — all level-3) already rendered live.

R2 Batch C is a PURE-D DEMOTION (no deletions, no supply changes): the dropped
region (L102-111) carries zero ``{{placeholders}}`` (triage-verified — all
template variables live above the cutoff), so demotion alone activates it
with zero new variable demands — confirmed by probe (real Registry+Composer,
route-exact context via the real ``build_chat_context`` seam from
``narrare_core.chat.chat_service_core``, mirroring
``apps/api/narrare/chat/_context.py``): compose no-raise, zero ``{{...}}``
residue, and the pre-change render is a byte-prefix of the post-change render
(pure tail activation, +499 chars).

* ``## Do NOT`` → ``### Do NOT``; its child header ``### Output Format`` →
  ``### Output Format`` sibling (kept at L3 — required-section checks and
  band_summary precedent only recognize L1-3 headings)
* prompt_version 1.4.0 → 1.5.0

PRE-EXISTING GAP (not this slice's, documented as a tripwire below): the CHAT
route declares only ``tone_instructions`` optional, but the template (since
CR-04, commit cbb49f76) demands ``{{timeline_position}}``, ``{{kb_context_
warnings}}``, ``{{kb_other}}`` and ``{{kb_suggested}}`` ABOVE the cutoff —
none of which the production chat seam (``build_prompt_context`` →
``build_chat_context`` + ``conversation_history``) supplies. A bare
production-shaped context therefore raises ``PromptVariableError`` at compose
today, independent of the demotion. The route-exact probe context declares
those four slots explicitly empty (the analysis-seam RULE-11 convention).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare_core.chat.chat_service_core import build_chat_context
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.errors import PromptVariableError
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

if TYPE_CHECKING:
    from narrare_core.prompts.context import PromptContext

# Distinctive content from the restored tail (dropped L102-111 pre-slice).
_DO_NOT_BULLETS = (
    "Do NOT write prose for the author unless they explicitly ask",
    "Do NOT provide personal advice, therapy, or counseling",
)
_OUTPUT_FORMAT_TAIL = (
    "### Output Format",
    "Respond in conversational prose",
)

# Sections that already rendered above the cutoff — must survive untouched.
_ALREADY_LIVE_SECTIONS = (
    "### Your Scope",
    "### Project Context",
    "### Style Profile",
    "### Character Voice Profiles",
    "### Author Voice",
    "### Conversation History",
    "### Guidelines",
    "### User Preferences",
)

# Template variables the production chat seam does not supply (pre-existing
# gap, above the cutoff). Declared explicitly empty per the analysis-seam
# RULE-11 convention so the optional-less CHAT route composes.
_UNSUPPLIED_TEMPLATE_VARS = (
    "timeline_position",
    "kb_context_warnings",
    "kb_other",
    "kb_suggested",
)


def _prompt_path():
    return bundled_prompts_root() / "writing" / "en" / "chat" / "system.md"


def _route_context() -> PromptContext:
    """Route-exact context via the real build_chat_context seam.

    Mirrors ``apps/api/narrare/chat/_context.py`` ``build_prompt_context``
    (project-less chat shape: empty title/genre, history attached), plus the
    four unsupplied template variables declared explicitly empty.
    """
    context = build_chat_context(project_title="", genre="", language="en")
    context.extra["conversation_history"] = "Author: How do I pace my opening chapter?"
    for var in _UNSUPPLIED_TEMPLATE_VARS:
        context.extra[var] = ""
    return context


async def _compose(ctx: PromptContext):
    """Compose the chat prompt via real registry + composer."""
    return await PromptComposer(PromptRegistry()).build(
        LLMIntent.CHAT, ctx, user_prompt="How do I pace my opening chapter?"
    )


class TestChatHeaderSurgery:
    """R2 Batch C (D): the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_section(self) -> None:
        """The registry-parsed System Prompt includes the demoted Do-NOT
        section and the Output Format section (L3 sibling, inside the
        L1-3 heading window) — proof both survive the extract_section
        boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(category="writing", language="en", mode="chat")
        assert "### Do NOT" in resolved.system_prompt, "demoted Do NOT section missing"
        assert "### Output Format" in resolved.system_prompt, "Output Format missing"
        for section in _ALREADY_LIVE_SECTIONS:
            assert section in resolved.system_prompt, f"regression: {section!r} dropped"

    def test_prompt_version_bumped_to_1_5_0(self) -> None:
        """Header surgery bumps the template minor version (1.4.0 → 1.5.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.5.0"


class TestChatDoNotActivation:
    """The activation contract: the Do-NOT + Output Format tail now renders."""

    async def test_route_context_compose_succeeds(self) -> None:
        """Route-exact context composes without PromptVariableError — zero new
        demands from the activated region (probe verdict as a pin)."""
        prompt = await _compose(_route_context())
        assert "writing craft assistant" in prompt.system

    async def test_composed_system_contains_do_not_tail(self) -> None:
        """The restored Do-NOT header, its distinctive bullets, and the
        Output Format section reach the composed system prompt."""
        prompt = await _compose(_route_context())
        assert "### Do NOT" in prompt.system
        for bullet in _DO_NOT_BULLETS:
            assert bullet in prompt.system, f"missing Do-NOT bullet {bullet!r}"
        for marker in _OUTPUT_FORMAT_TAIL:
            assert marker in prompt.system, f"missing Output Format marker {marker!r}"

    async def test_composed_system_carries_no_placeholder_residue(self) -> None:
        """rg-style containment: the render leaks no ``{{...}}`` token."""
        prompt = await _compose(_route_context())
        assert "{{" not in prompt.system, "placeholder residue in render"

    async def test_bare_seam_context_compose_raises_preexisting_gap(self) -> None:
        """PRE-EXISTING GAP TRIPWIRE (above the cutoff, not this slice).

        The bare production-shaped seam context (``build_chat_context`` +
        ``conversation_history``, no explicit-empty declarations) does NOT
        compose: the CHAT route declares only ``tone_instructions`` optional
        while the template (since CR-04) demands ``{{timeline_position}}``
        and friends — none supplied by the chat service seam. This pins the
        latent defect so the fix (supply wiring or route optionals) flips
        this test deliberately instead of silently.
        """
        context = build_chat_context(project_title="", genre="", language="en")
        context.extra["conversation_history"] = "Author: Hello"
        with pytest.raises(PromptVariableError, match="timeline_position"):
            await _compose(context)
