"""LLMIntent.VOICE / voice_check route + prompt-path-compliance (ADR-057 D3).

Layer-1 test for the WRITE-010 voice-check prompt surface. ADR-057 Decision 3
adds a second governed context_mode ``voice_check`` to the routeable
``LLMIntent.VOICE`` intent (alongside ``character_voice`` from ANAL-008 / ADR-055).
``voice_check`` is a **flag+score checker** prompt — a different intent from the
*profiling* ``character_voice`` prompt — so it gets its own governed EN template.

This is the ADR-046 §D.1 Prompt-Path-Compliance test for VOICE/`voice_check` at
the Layer-1 (prompt-surface) level: it proves the route resolves through
PromptComposer Mode 1 to the governed bundled template
``_bundled/analysis/en/voice_check/system.md`` with **no inline fallback** and
**no ``composer is None`` path**. (The resolving *service* lands in Layer 2/3;
its own ``*_prompt_path_compliance.py`` test will be added then.)

RULE-11 lesson (from character_voice Layer 1): the route MUST declare the same
``optional_variables`` the template references, or ``prepare_variables_for_template``
raises ``PromptVariableError`` for projects lacking them. ``voice_check`` inherits
the VOICE intent's optional set, so the KB world-context + preference variables
the template references are guaranteed to render empty (not crash) when absent.

See:
    - ``docs/architecture/decisions/ADR-057-voice-check-checking-path-contract.md`` Decision 3
    - ``docs/_shared/CONSTRAINTS.md`` RULE-02 / RULE-02b / RULE-11
"""

from __future__ import annotations

import pytest

from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.route_table import (
    INTENT_TO_MODE,
    ROUTE_CONFIGS,
)
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.errors import PromptRouteNotConfiguredError
from tests.unit.core._bundled import bundled_prompts_root

_BUNDLED_ROOT = bundled_prompts_root()
_VOICE_CHECK_TEMPLATE = _BUNDLED_ROOT / "analysis" / "en" / "voice_check" / "system.md"

# Variables the voice_check template references. RULE-11: every one of these
# MUST be declared optional on the VOICE route config (inherited by voice_check)
# so a project lacking them renders empty rather than crashing the variable engine.
_VOICE_CHECK_TEMPLATE_VARS = frozenset(
    {
        "project_title",
        "genre",
        "writing_language",
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_relationships",
        "user_preferences",
        "avoidance_patterns",
    }
)


class TestVoiceCheckRouteability:
    """ADR-057 D3 — voice_check is the second governed context_mode on VOICE."""

    def test_voice_check_is_in_allowed_context_modes(self) -> None:
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        assert "voice_check" in config.allowed_context_modes

    def test_voice_route_is_multi_mode(self) -> None:
        """character_voice (profiler), voice_check (checker), and voice_drift
        (longitudinal trend classifier) are all allowed VOICE context_modes.

        ADR-073 D3 added voice_drift as the third governed mode; author_voice
        (ANAL-007) remains deferred (Phase 2).
        """
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        assert config.allowed_context_modes == frozenset(
            {"character_voice", "voice_check", "voice_drift"}
        )

    def test_default_mode_still_character_voice(self) -> None:
        """voice_check is opt-in; the VOICE default mode stays character_voice."""
        assert INTENT_TO_MODE[LLMIntent.VOICE] == "character_voice"

    def test_voice_check_inherits_template_optional_variables(self) -> None:
        """RULE-11: every template variable must be declared optional on the route.

        A project may legitimately lack KB world context (no characters /
        locations / factions / relationships). Those placeholders MUST render as
        empty rather than raise ``PromptVariableError``. voice_check resolves the
        VOICE intent's shared ``optional_variables``, so all template-referenced
        vars must be present there (mirrors the character_voice Layer-1 fix).
        """
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        missing = _VOICE_CHECK_TEMPLATE_VARS - config.optional_variables
        assert not missing, (
            f"voice_check template references variables not declared optional on the "
            f"VOICE route config (RULE-11 crash risk): {sorted(missing)}"
        )


class TestVoiceCheckRouteResolution:
    """resolve_prompt_route honours the voice_check route (RULE-02b)."""

    def test_explicit_voice_check_mode_resolves(self) -> None:
        route = resolve_prompt_route(LLMIntent.VOICE, "voice_check")
        assert route.category == "analysis"
        assert route.mode == "voice_check"

    def test_character_voice_still_resolves(self) -> None:
        """Adding voice_check did not break the existing character_voice route."""
        route = resolve_prompt_route(LLMIntent.VOICE, "character_voice")
        assert route.mode == "character_voice"

    def test_undeferred_voice_modes_are_still_rejected(self) -> None:
        """author_voice remains deferred — not yet a governed route.

        ADR-073 D3 promoted voice_drift to a governed route (ANAL-009 Phase 1);
        it is no longer rejected. Only author_voice (ANAL-007, Phase 2 deferral)
        remains un-governed.
        """
        with pytest.raises(PromptRouteNotConfiguredError, match=LLMIntent.VOICE.value):
            resolve_prompt_route(LLMIntent.VOICE, "author_voice")


class TestVoiceCheckPromptPathCompliance:
    """ADR-046 §D.1 — VOICE/voice_check resolves via PromptComposer Mode 1.

    The system prompt must come from the governed bundled template, not an
    inline fallback or a ``composer is None`` path (RULE-02b).
    """

    def test_bundled_voice_check_template_exists(self) -> None:
        assert _VOICE_CHECK_TEMPLATE.is_file(), (
            f"Governed EN template missing: {_VOICE_CHECK_TEMPLATE}"
        )

    async def test_registry_resolves_bundled_voice_check(self) -> None:
        registry = PromptRegistry()
        resolved = await registry.resolve(
            category="analysis",
            language="en",
            mode="voice_check",
        )
        # source="bundled" proves Mode-1 governed resolution (no db / project /
        # user override in the test environment), and the system prompt carries
        # the checker template's distinctive instruction rather than an inline fallback.
        assert resolved.source == "bundled"
        assert resolved.category == "analysis"
        assert resolved.mode == "voice_check"
        # voice_check is a flag+score CHECKER, not a profiler — the distinctive
        # instruction distinguishes it from the character_voice template.
        assert "voice consistency" in resolved.system_prompt.lower()

    async def test_composer_builds_voice_check_from_bundled_template(self) -> None:
        """Full Mode-1 composition through PromptComposer — no inline fallback."""
        registry = PromptRegistry()
        composer = PromptComposer(registry)
        # ``mode`` drives route resolution (composer resolves via context.mode);
        # setting it to voice_check selects the checker route over the default
        # character_voice profiler route.
        ctx = PromptContext(
            language="en",
            mode="voice_check",
            writing_language="en",
            project_title="Echoes of the Thornwall",
            genre="Fantasy",
            user_preferences="Concise prose.",
            avoidance_patterns="Cliches.",
            extra={"kb_characters": "Elena; Mara"},
        )

        result = await composer.build(LLMIntent.VOICE, ctx)

        # The composed system must carry content unique to the governed bundled
        # checker template (proving it was NOT produced by an inline fallback or
        # by the character_voice profiler template).
        assert "voice consistency" in result.system.lower()
        assert "Echoes of the Thornwall" in result.system
        # {{writing_language}} (CR-01) substituted, no raw placeholder remains.
        assert "{{writing_language}}" not in result.system
        assert "{{kb_characters}}" not in result.system
