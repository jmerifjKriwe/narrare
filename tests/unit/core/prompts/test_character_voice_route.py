"""LLMIntent.VOICE / character_voice route + prompt-path-compliance (ADR-055 D4).

Layer-1 test for the ANAL-008 character-voice prompt surface. ADR-055 Decision 4
promotes ``LLMIntent.VOICE`` from non-routeable to a multi-mode routeable intent
whose first context_mode is ``character_voice`` (voice_check, voice_drift, and
author_voice were added later by ADR-057 / ADR-073 / ADR-074 respectively).
This mirrors how ``LLMIntent.PLAN`` serves outline / timeline / character_arc /
timeline_extraction.

This is the ADR-046 §D.1 Prompt-Path-Compliance test for the VOICE route at the
Layer-1 (prompt-surface) level: it proves the route resolves through
PromptComposer Mode 1 to the governed bundled template
``_bundled/analysis/en/character_voice/system.md`` with **no inline fallback**
and **no ``composer is None`` path**. (The resolving *service* lands in Layer 2/3;
its own ``*_prompt_path_compliance.py`` test will be added then.)

See:
    - ``docs/architecture/decisions/ADR-055-character-voice-contract.md`` Decision 4
    - ``docs/_shared/CONSTRAINTS.md`` RULE-02 / RULE-02b
"""

from __future__ import annotations

from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.route_table import (
    INTENT_TO_CATEGORY,
    INTENT_TO_MODE,
    NON_ROUTEABLE_INTENTS,
    ROUTE_CONFIGS,
)
from narrare_core.prompts.routes import resolve_prompt_route
from tests.unit.core._bundled import bundled_prompts_root

_BUNDLED_ROOT = bundled_prompts_root()
_CHARACTER_VOICE_TEMPLATE = _BUNDLED_ROOT / "analysis" / "en" / "character_voice" / "system.md"


class TestVoiceIntentRouteability:
    """ADR-055 D4 — VOICE is promoted to a routeable analysis intent."""

    def test_voice_is_no_longer_non_routeable(self) -> None:
        """VOICE must be removed from NON_ROUTEABLE_INTENTS (ADR-055 D4)."""
        assert LLMIntent.VOICE not in NON_ROUTEABLE_INTENTS

    def test_voice_category_is_analysis(self) -> None:
        assert INTENT_TO_CATEGORY[LLMIntent.VOICE] == "analysis"

    def test_voice_default_mode_is_character_voice(self) -> None:
        assert INTENT_TO_MODE[LLMIntent.VOICE] == "character_voice"

    def test_voice_route_config_has_character_voice_context_mode(self) -> None:
        config = ROUTE_CONFIGS[LLMIntent.VOICE]
        assert config.category == "analysis"
        assert config.default_mode == "character_voice"
        # character_voice is the default governed mode. ADR-057 D3 added a
        # second governed context_mode, voice_check (a flag+score checker for
        # WRITE-010); ADR-073 D3 added a third, voice_drift (a longitudinal
        # trend classifier for ANAL-009 Phase 1); ADR-074 + ANAL-007 added a
        # fourth, author_voice (an author-voice profiler for narrator prose);
        # ANAL-009 Phase 2B added a fifth, author_voice_drift (a longitudinal
        # narrator trend classifier).
        # See test_voice_check_route.py / test_voice_drift_route.py /
        # test_author_voice_route.py / test_author_voice_drift_route.py for the
        # other modes' coverage.
        assert config.allowed_context_modes == frozenset(
            {
                "character_voice",
                "voice_check",
                "voice_drift",
                "author_voice",
                "author_voice_drift",
            }
        )


class TestVoiceRouteResolution:
    """resolve_prompt_route honours the character_voice route (RULE-02b)."""

    def test_explicit_character_voice_mode_resolves(self) -> None:
        route = resolve_prompt_route(LLMIntent.VOICE, "character_voice")
        assert route.category == "analysis"
        assert route.mode == "character_voice"

    def test_default_resolution_uses_character_voice(self) -> None:
        """Without an explicit context_mode, VOICE resolves to its default mode."""
        route = resolve_prompt_route(LLMIntent.VOICE)
        assert route.mode == "character_voice"


class TestVoicePromptPathCompliance:
    """ADR-046 §D.1 — VOICE/character_voice resolves via PromptComposer Mode 1.

    The system prompt must come from the governed bundled template, not an
    inline fallback or a ``composer is None`` path (RULE-02b).
    """

    def test_bundled_character_voice_template_exists(self) -> None:
        assert _CHARACTER_VOICE_TEMPLATE.is_file(), (
            f"Governed EN template missing: {_CHARACTER_VOICE_TEMPLATE}"
        )

    async def test_registry_resolves_bundled_character_voice(self) -> None:
        registry = PromptRegistry()
        resolved = await registry.resolve(
            category="analysis",
            language="en",
            mode="character_voice",
        )
        # source="bundled" proves Mode-1 governed resolution (no db / project /
        # user override in the test environment), and the system prompt carries
        # the template's distinctive instruction rather than an inline fallback.
        assert resolved.source == "bundled"
        assert resolved.category == "analysis"
        assert resolved.mode == "character_voice"
        assert "character voice" in resolved.system_prompt.lower()

    async def test_composer_builds_voice_from_bundled_template(self) -> None:
        """Full Mode-1 composition through PromptComposer — no inline fallback."""
        registry = PromptRegistry()
        composer = PromptComposer(registry)
        ctx = PromptContext(
            language="en",
            writing_language="en",
            project_title="Echoes of the Thornwall",
            genre="Fantasy",
            user_preferences="Concise prose.",
            avoidance_patterns="Cliches.",
            extra={"kb_characters": "Elena; Mara"},
        )

        result = await composer.build(LLMIntent.VOICE, ctx)

        # The composed system must carry content unique to the governed bundled
        # template (proving it was NOT produced by an inline fallback string).
        assert "character voice" in result.system.lower()
        assert "Echoes of the Thornwall" in result.system
        # {{writing_language}} (CR-01) substituted, no raw placeholder remains.
        assert "{{writing_language}}" not in result.system
        assert "{{kb_characters}}" not in result.system
