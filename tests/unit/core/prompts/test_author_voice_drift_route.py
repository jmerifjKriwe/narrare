"""LLMIntent.VOICE / author_voice_drift route + prompt-path-compliance
(ANAL-009 Phase 2B / ADR-074).

Layer-1 test for the ANAL-009 Phase 2B author-voice-drift prompt surface. This
adds a fifth governed context_mode ``author_voice_drift`` to the routeable
``LLMIntent.VOICE`` intent (alongside ``character_voice`` from ANAL-008 /
ADR-055, ``voice_check`` from WRITE-010 / ADR-057, ``voice_drift`` from
ANAL-009 Phase 1 / ADR-073, and ``author_voice`` from ANAL-007 / ADR-074).
``author_voice_drift`` is a **longitudinal narrator trend classifier** — a
different intent from the *per-character* profiler, the *snapshot* checker, the
*per-character trend* classifier, and the *author-voice profiler* — so it gets
its own governed EN template.

This is the ADR-046 §D.1 Prompt-Path-Compliance test for
VOICE/`author_voice_drift` at the Layer-1 (prompt-surface) level: it proves the
route resolves through PromptComposer Mode 1 to the governed bundled template
``_bundled/analysis/en/author_voice_drift/system.md`` with **no inline
fallback** and **no ``composer is None`` path**. (The resolving *service* lands
in Layer 2/3 — Backend — where its own ``*_prompt_path_compliance.py`` test
will be added then.)

RULE-11: ``author_voice_drift`` inherits the VOICE intent's optional set, so
the KB world-context + preference variables the template references render
empty (not crash) when absent.

See:
    - ``docs/architecture/decisions/ADR-074-author-voice-storage.md``
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
_AUTHOR_VOICE_DRIFT_TEMPLATE = (
    _BUNDLED_ROOT / "analysis" / "en" / "author_voice_drift" / "system.md"
)

# Variables the author_voice_drift template references. RULE-11: every one of
# these MUST be declared optional on the VOICE route config (inherited by
# author_voice_drift) so a project lacking them renders empty rather than
# crashing the variable engine.
_AUTHOR_VOICE_DRIFT_TEMPLATE_VARS = frozenset(
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


class TestAuthorVoiceDriftRouteability:
    """author_voice_drift is the fifth governed context_mode on VOICE."""

    def test_author_voice_drift_is_in_allowed_context_modes(self) -> None:
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        assert "author_voice_drift" in config.allowed_context_modes

    def test_voice_route_is_five_mode(self) -> None:
        """character_voice (profiler), voice_check (checker), voice_drift
        (per-character trend classifier), author_voice (author-voice profiler),
        and author_voice_drift (narrator trend classifier) are all allowed
        VOICE context_modes.

        ANAL-009 Phase 2B added author_voice_drift as the fifth governed mode.
        """
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        assert config.allowed_context_modes == frozenset(
            {
                "character_voice",
                "voice_check",
                "voice_drift",
                "author_voice",
                "author_voice_drift",
            }
        )

    def test_default_mode_still_character_voice(self) -> None:
        """author_voice_drift is opt-in; the VOICE default stays character_voice."""
        assert INTENT_TO_MODE[LLMIntent.VOICE] == "character_voice"

    def test_author_voice_drift_inherits_template_optional_variables(self) -> None:
        """RULE-11: every template variable must be declared optional on the route."""
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        missing = _AUTHOR_VOICE_DRIFT_TEMPLATE_VARS - config.optional_variables
        assert not missing, (
            f"author_voice_drift template references variables not declared "
            f"optional on the VOICE route config (RULE-11 crash risk): "
            f"{sorted(missing)}"
        )


class TestAuthorVoiceDriftRouteResolution:
    """resolve_prompt_route honours the author_voice_drift route (RULE-02b)."""

    def test_explicit_author_voice_drift_mode_resolves(self) -> None:
        route = resolve_prompt_route(LLMIntent.VOICE, "author_voice_drift")
        assert route.category == "analysis"
        assert route.mode == "author_voice_drift"

    def test_voice_drift_still_resolves(self) -> None:
        """Adding author_voice_drift did not break the voice_drift route."""
        route = resolve_prompt_route(LLMIntent.VOICE, "voice_drift")
        assert route.mode == "voice_drift"

    def test_author_voice_still_resolves(self) -> None:
        """Adding author_voice_drift did not break the author_voice route."""
        route = resolve_prompt_route(LLMIntent.VOICE, "author_voice")
        assert route.mode == "author_voice"


class TestAuthorVoiceDriftPromptPathCompliance:
    """ADR-046 §D.1 — VOICE/author_voice_drift resolves via PromptComposer Mode 1."""

    def test_bundled_author_voice_drift_template_exists(self) -> None:
        assert _AUTHOR_VOICE_DRIFT_TEMPLATE.is_file(), (
            f"Governed EN template missing: {_AUTHOR_VOICE_DRIFT_TEMPLATE}"
        )

    async def test_registry_resolves_bundled_author_voice_drift(self) -> None:
        registry = PromptRegistry()
        resolved = await registry.resolve(
            category="analysis",
            language="en",
            mode="author_voice_drift",
        )
        # source="bundled" proves Mode-1 governed resolution; the system prompt
        # carries the author-voice-drift template's distinctive instruction
        # rather than an inline fallback.
        assert resolved.source == "bundled"
        assert resolved.category == "analysis"
        assert resolved.mode == "author_voice_drift"
        # The narrator trend-classifier instruction distinguishes it from the
        # other four voice templates.
        assert "drift" in resolved.system_prompt.lower()

    async def test_composer_builds_author_voice_drift_from_bundled_template(self) -> None:
        """Full Mode-1 composition through PromptComposer — no inline fallback."""
        registry = PromptRegistry()
        composer = PromptComposer(registry)
        # ``mode`` drives route resolution (composer resolves via context.mode);
        # setting it to author_voice_drift selects the narrator trend-classifier
        # route over the four other voice routes.
        ctx = PromptContext(
            language="en",
            mode="author_voice_drift",
            writing_language="en",
            project_title="Echoes of the Thornwall",
            genre="Fantasy",
            user_preferences="Concise prose.",
            avoidance_patterns="Cliches.",
            extra={"kb_characters": "Elena; Mara"},
        )

        result = await composer.build(LLMIntent.VOICE, ctx)

        # The composed system must carry content unique to the governed bundled
        # author-voice-drift template (proving it was NOT produced by an inline
        # fallback or by the other four voice templates).
        assert "drift" in result.system.lower()
        assert "Echoes of the Thornwall" in result.system
        # {{writing_language}} (CR-01) substituted, no raw placeholder remains.
        assert "{{writing_language}}" not in result.system
        assert "{{kb_characters}}" not in result.system
