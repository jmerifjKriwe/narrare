"""LLMIntent.VOICE / voice_drift route + prompt-path-compliance (ADR-073 D3).

Layer-1 test for the ANAL-009 Phase 1 voice-drift prompt surface. ADR-073
Decision 3 adds a third governed context_mode ``voice_drift`` to the routeable
``LLMIntent.VOICE`` intent (alongside ``character_voice`` from ANAL-008 /
ADR-055 and ``voice_check`` from WRITE-010 / ADR-057). ``voice_drift`` is a
**longitudinal trend classifier** prompt — a different intent from the
*profiling* ``character_voice`` prompt and the *snapshot checking* ``voice_check``
prompt — so it gets its own governed EN template.

This is the ADR-046 §D.1 Prompt-Path-Compliance test for VOICE/`voice_drift`
at the Layer-1 (prompt-surface) level: it proves the route resolves through
PromptComposer Mode 1 to the governed bundled template
``_bundled/analysis/en/voice_drift/system.md`` with **no inline fallback** and
**no ``composer is None`` path**. (The resolving *service* lands in Layer 2/3
— Backend Task 2 — where its own ``*_prompt_path_compliance.py`` test will be
added then.)

RULE-11 lesson (from character_voice + voice_check Layer 1): the route MUST
declare the same ``optional_variables`` the template references, or
``prepare_variables_for_template`` raises ``PromptVariableError`` for projects
lacking them. ``voice_drift`` inherits the VOICE intent's optional set, so the
KB world-context + preference variables the template references are guaranteed
to render empty (not crash) when absent.

See:
    - ``docs/architecture/decisions/ADR-073-voice-drift-character.md`` Decision 3
    - ``docs/_shared/CONSTRAINTS.md`` RULE-02 / RULE-02b / RULE-11
"""

from __future__ import annotations

from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.route_table import (
    INTENT_TO_MODE,
    ROUTE_CONFIGS,
)
from narrare_core.prompts.routes import resolve_prompt_route
from tests.unit.core._bundled import bundled_prompts_root

_BUNDLED_ROOT = bundled_prompts_root()
_VOICE_DRIFT_TEMPLATE = _BUNDLED_ROOT / "analysis" / "en" / "voice_drift" / "system.md"

# Variables the voice_drift template references. RULE-11: every one of these
# MUST be declared optional on the VOICE route config (inherited by voice_drift)
# so a project lacking them renders empty rather than crashing the variable engine.
_VOICE_DRIFT_TEMPLATE_VARS = frozenset(
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


class TestVoiceDriftRouteability:
    """ADR-073 D3 — voice_drift is the third governed context_mode on VOICE."""

    def test_voice_drift_is_in_allowed_context_modes(self) -> None:
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        assert "voice_drift" in config.allowed_context_modes

    def test_voice_route_is_three_mode(self) -> None:
        """character_voice (profiler), voice_check (checker), voice_drift
        (longitudinal trend classifier), and author_voice (author-voice
        profiler) are all allowed VOICE context_modes.

        ADR-074 + ANAL-007 added author_voice as the fourth governed mode.
        """
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        assert config.allowed_context_modes == frozenset(
            {"character_voice", "voice_check", "voice_drift", "author_voice"}
        )

    def test_default_mode_still_character_voice(self) -> None:
        """voice_drift is opt-in; the VOICE default mode stays character_voice."""
        assert INTENT_TO_MODE[LLMIntent.VOICE] == "character_voice"

    def test_voice_drift_inherits_template_optional_variables(self) -> None:
        """RULE-11: every template variable must be declared optional on the route.

        A project may legitimately lack KB world context (no characters /
        locations / factions / relationships). Those placeholders MUST render as
        empty rather than raise ``PromptVariableError``. voice_drift resolves the
        VOICE intent's shared ``optional_variables``, so all template-referenced
        vars must be present there (mirrors the character_voice + voice_check
        Layer-1 fixes).
        """
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        missing = _VOICE_DRIFT_TEMPLATE_VARS - config.optional_variables
        assert not missing, (
            f"voice_drift template references variables not declared optional on the "
            f"VOICE route config (RULE-11 crash risk): {sorted(missing)}"
        )


class TestVoiceDriftRouteResolution:
    """resolve_prompt_route honours the voice_drift route (RULE-02b)."""

    def test_explicit_voice_drift_mode_resolves(self) -> None:
        route = resolve_prompt_route(LLMIntent.VOICE, "voice_drift")
        assert route.category == "analysis"
        assert route.mode == "voice_drift"

    def test_character_voice_still_resolves(self) -> None:
        """Adding voice_drift did not break the existing character_voice route."""
        route = resolve_prompt_route(LLMIntent.VOICE, "character_voice")
        assert route.mode == "character_voice"

    def test_voice_check_still_resolves(self) -> None:
        """Adding voice_drift did not break the existing voice_check route."""
        route = resolve_prompt_route(LLMIntent.VOICE, "voice_check")
        assert route.mode == "voice_check"


class TestVoiceDriftPromptPathCompliance:
    """ADR-046 §D.1 — VOICE/voice_drift resolves via PromptComposer Mode 1.

    The system prompt must come from the governed bundled template, not an
    inline fallback or a ``composer is None`` path (RULE-02b).
    """

    def test_bundled_voice_drift_template_exists(self) -> None:
        assert _VOICE_DRIFT_TEMPLATE.is_file(), (
            f"Governed EN template missing: {_VOICE_DRIFT_TEMPLATE}"
        )

    async def test_registry_resolves_bundled_voice_drift(self) -> None:
        registry = PromptRegistry()
        resolved = await registry.resolve(
            category="analysis",
            language="en",
            mode="voice_drift",
        )
        # source="bundled" proves Mode-1 governed resolution (no db / project /
        # user override in the test environment), and the system prompt carries
        # the drift template's distinctive instruction rather than an inline fallback.
        assert resolved.source == "bundled"
        assert resolved.category == "analysis"
        assert resolved.mode == "voice_drift"
        # voice_drift is a longitudinal TREND CLASSIFIER, not a profiler or a
        # snapshot checker — the distinctive instruction distinguishes it from
        # both the character_voice and voice_check templates.
        assert "drift" in resolved.system_prompt.lower()

    async def test_composer_builds_voice_drift_from_bundled_template(self) -> None:
        """Full Mode-1 composition through PromptComposer — no inline fallback."""
        registry = PromptRegistry()
        composer = PromptComposer(registry)
        # ``mode`` drives route resolution (composer resolves via context.mode);
        # setting it to voice_drift selects the drift-classifier route over the
        # default character_voice profiler route and the voice_check checker route.
        ctx = PromptContext(
            language="en",
            mode="voice_drift",
            writing_language="en",
            project_title="Echoes of the Thornwall",
            genre="Fantasy",
            user_preferences="Concise prose.",
            avoidance_patterns="Cliches.",
            extra={"kb_characters": "Elena; Mara"},
        )

        result = await composer.build(LLMIntent.VOICE, ctx)

        # The composed system must carry content unique to the governed bundled
        # drift template (proving it was NOT produced by an inline fallback or
        # by the character_voice / voice_check templates).
        assert "drift" in result.system.lower()
        assert "Echoes of the Thornwall" in result.system
        # {{writing_language}} (CR-01) substituted, no raw placeholder remains.
        assert "{{writing_language}}" not in result.system
        assert "{{kb_characters}}" not in result.system
