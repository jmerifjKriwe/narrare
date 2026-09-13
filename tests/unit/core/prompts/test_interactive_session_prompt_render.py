"""Render-level tests for the interactive_session composed prompt (R2 Slice C2).

Before R2-C2 (2026-09-11): the interactive_session template's rogue
``## Output Format`` (L115) and ``## Do NOT`` (L123) level-2 headers
truncated the System Prompt at parse time (extract_section boundary), so
Output Format, User Preferences, the Do NOT rules and the Constraints
(closing ``{{avoidance_patterns}}`` line) never rendered.

R2-C2 demotes both headers (template v1.3.0 → v1.4.0) leaving
``## System Prompt`` as the only level-2 header. Empirical probe evidence
(/tmp/opencode/probe_r2c2.py, real PromptRegistry + PromptComposer):

* The demotion introduces ZERO new variable demands — the bare WS-turn
  context demands exactly ``kb_characters, kb_locations, chapter_outline,
  word_target`` both pre- and post-demotion (all live in the always-active
  region; the demoted region only activates ``user_preferences`` /
  ``avoidance_patterns``, which are PromptContext dataclass fields and
  therefore always resolve).
* The bare WS-turn context (``ws_turn_service._build_prompt_context``)
  does not supply the four demanded vars — a PRE-EXISTING production gap
  (the interview mode template shows the same demand), to be closed by a
  dedicated WS supply slice. The demand-set pin below guards that this
  slice does not widen the gap; the tests supply the four vars test-side
  to pin the restored render.
"""

from __future__ import annotations

import re

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.errors import PromptVariableError
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# The WS-follow-up supply set: demanded by the bare ws_turn PromptContext
# in exactly this order. Slice-3 word_target migration (2026-09-13): the
# fourth demand is now ``word_target_line`` (label-in-value) — the template's
# static ``Word target: {{word_target}}`` line was replaced by an appended
# ``{{word_target_line}}`` placeholder.
_WS_SUPPLY_VARS = (
    "kb_characters",
    "kb_locations",
    "chapter_outline",
    "word_target_line",
)

_PREF_SENTINEL = "PREF: prefers tight third-person limited POV."
_AVOID_SENTINEL = "AVOID: no dream sequences, no head-hopping."


def _prompt_path():
    return bundled_prompts_root() / "writing" / "en" / "interactive_session" / "system.md"


def _ws_turn_context(**extra: str) -> PromptContext:
    """Bare ws_turn_service._build_prompt_context shape (+ test-side supply)."""
    return PromptContext(
        language="en",
        mode="interactive_session",
        author_instructions="Continue the scene: Mara opens the lighthouse door.",
        extra=dict(extra),
    )


def _compose(ctx: PromptContext):
    """Compose the interactive_session prompt via real registry + composer."""
    return PromptComposer(PromptRegistry()).build(LLMIntent.WRITE, ctx)


async def _compose_supplied() -> ComposedPrompt:
    """Compose with the WS supply set + adaptive sentinels (test-side)."""
    ctx = _ws_turn_context(
        **{var: f"<test:{var}>" for var in _WS_SUPPLY_VARS},
    )
    ctx.user_preferences = _PREF_SENTINEL
    ctx.avoidance_patterns = _AVOID_SENTINEL
    return await _compose(ctx)


class TestInteractiveSessionHeaderDemotion:
    """R2-C2: the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_sections(self) -> None:
        """The registry-parsed System Prompt includes the restored tail
        sections — proof they survive the extract_section boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(
            category="writing", language="en", mode="interactive_session"
        )
        for section in (
            "### Output Format",
            "### User Preferences",
            "### Do NOT",
            "### Constraints",
        ):
            assert section in resolved.system_prompt, f"missing {section!r}"
        # No level-2 header survives parsing (the single header is consumed
        # by extract_section itself).
        assert not [ln for ln in resolved.system_prompt.splitlines() if re.match(r"^## ", ln)]

    def test_prompt_version_bumped_to_1_5_0(self) -> None:
        """Slice-3 word_target migration bumps the minor version
        (1.4.0 → 1.5.0): static label line → {{word_target_line}}."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.5.0"


class TestInteractiveSessionRender:
    """The composed system prompt renders the restored sections + sentinels."""

    async def test_compose_renders_demoted_sections(self) -> None:
        """Do NOT rules + Constraints reach the composed system prompt."""
        prompt = await _compose_supplied()
        for fragment in (
            "### Do NOT",
            "Do NOT change the narrative perspective without author approval",
            "### Constraints",
            "Respect the author's avoidance patterns:",
        ):
            assert fragment in prompt.system, f"missing {fragment!r}"

    async def test_compose_renders_adaptive_sentinels(self) -> None:
        """user_preferences / avoidance_patterns (demotion-activated
        placeholders) render their adaptive values in the system prompt."""
        prompt = await _compose_supplied()
        assert _PREF_SENTINEL in prompt.system
        assert _AVOID_SENTINEL in prompt.system

    async def test_author_instructions_render_xml_wrapped_in_system(self) -> None:
        """The WS direction renders XML-wrapped at the governed
        <user_instructions> site (never as a bare user-channel fallback)."""
        prompt = await _compose_supplied()
        assert (
            "<user_instructions>Continue the scene: Mara opens the lighthouse door."
            "</user_instructions>" in prompt.system
        )

    async def test_compose_demand_set_unchanged_by_demotion(self) -> None:
        """Neutrality pin: the bare WS context demands exactly the four
        pre-existing supply vars, in probe order — the demotion must not
        widen the gap (user_preferences / avoidance_patterns resolve as
        PromptContext fields and never demand)."""
        ctx = _ws_turn_context()
        demanded: list[str] = []
        for _ in range(len(_WS_SUPPLY_VARS)):
            try:
                await _compose(ctx)
            except PromptVariableError as exc:
                var = str(exc).split("'")[1]
                demanded.append(var)
                ctx.extra[var] = f"<test:{var}>"
        assert demanded == list(_WS_SUPPLY_VARS)
        # With the full set supplied, the compose succeeds.
        prompt = await _compose(ctx)
        assert prompt.system
