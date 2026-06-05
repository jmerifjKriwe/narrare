"""Tests for prompts/composer.py"""

from __future__ import annotations

from pathlib import Path

import pytest

from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import ResolvedPrompt
from narrare_core.prompts.routes import (
    _CONTEXT_MODE_REQUIRED_INTENTS,
    _INTENT_TO_CATEGORY,
    _INTENT_TO_MODE,
    _NON_ROUTEABLE_INTENTS,
)
from narrare_core.shared.errors import PromptRouteNotConfiguredError, PromptVariableError

_BUNDLED_ROOT = Path(__file__).parents[4] / "packages/core/narrare_core/prompts/_bundled"
_CR02_TARGETS = {
    LLMIntent.KB_CREATE,
    LLMIntent.ANALYSE,
    LLMIntent.SENTIMENT,
    LLMIntent.VOICE,
    LLMIntent.PLAN,
    LLMIntent.GENERATE,
    LLMIntent.TITLE_GENERATE,
    LLMIntent.EXTRACT,
    LLMIntent.RESEARCH,
}


def _make_resolved(system: str = "System.", first: str | None = "Hello!") -> ResolvedPrompt:
    return ResolvedPrompt(
        system_prompt=system,
        first_message=first,
        source="bundled",
        category="writing",
        language="en",
        mode="new_chapter",
        metadata={},
    )


class FakePromptRegistry:
    """Minimal fake for PromptRegistry — returns programmable resolved prompts."""

    def __init__(self, resolved: ResolvedPrompt | None = None) -> None:
        self._resolved = resolved or _make_resolved()
        self.calls: list[dict[str, str | None]] = []

    async def resolve(
        self,
        *,
        category: str,
        language: str,
        mode: str,
        genre: str | None = None,
        db_content: str | None = None,
    ) -> ResolvedPrompt:
        self.calls.append(
            {
                "category": category,
                "language": language,
                "mode": mode,
                "genre": genre,
                "db_content": db_content,
            }
        )
        return self._resolved


@pytest.fixture
def fake_registry() -> FakePromptRegistry:
    return FakePromptRegistry()


@pytest.fixture
def composer(fake_registry: FakePromptRegistry) -> PromptComposer:
    return PromptComposer(fake_registry)  # type: ignore[arg-type]


class TestPromptComposerBuild:
    async def test_returns_composed_prompt(self, composer: PromptComposer) -> None:
        ctx = PromptContext(language="en", project_title="My Novel")
        result = await composer.build(LLMIntent.WRITE, ctx)
        assert isinstance(result, ComposedPrompt)
        assert result.system == "System."
        assert result.user == "Hello!"

    async def test_user_prompt_overrides_first_message(self, composer: PromptComposer) -> None:
        ctx = PromptContext(language="en")
        result = await composer.build(LLMIntent.WRITE, ctx, user_prompt="Custom prompt.")
        assert result.user == "Custom prompt."

    async def test_variables_substituted_in_system(self) -> None:
        fake_registry = FakePromptRegistry(_make_resolved(system="Write for {{project_title}}."))
        composer = PromptComposer(fake_registry)  # type: ignore[arg-type]
        ctx = PromptContext(language="en", project_title="Echoes of the Thornwall")
        result = await composer.build(LLMIntent.WRITE, ctx)
        assert "Echoes of the Thornwall" in result.system

    async def test_strict_preflight_rejects_missing_required_route_variable(self) -> None:
        fake_registry = FakePromptRegistry(_make_resolved(system="Outline: {{chapter_outline}}"))
        composer = PromptComposer(fake_registry)  # type: ignore[arg-type]

        with pytest.raises(PromptVariableError, match="chapter_outline"):
            await composer.build(LLMIntent.WRITE, PromptContext(language="en"))

    async def test_optional_generated_context_defaults_to_empty_string(self) -> None:
        fake_registry = FakePromptRegistry(
            _make_resolved(system="Optional lower-priority suggestions: {{kb_suggested}}")
        )
        composer = PromptComposer(fake_registry)  # type: ignore[arg-type]

        result = await composer.build(LLMIntent.WRITE, PromptContext(language="en"))

        assert "{{kb_suggested}}" not in result.system
        assert result.system == "Optional lower-priority suggestions: "


class TestPromptRouteGovernance:
    """Regression coverage for INFRA-012 PromptComposer route governance."""

    @pytest.mark.parametrize("intent", sorted(_INTENT_TO_MODE, key=str))
    def test_routeable_default_mappings_have_bundled_en_targets(
        self,
        intent: LLMIntent,
    ) -> None:
        category = _INTENT_TO_CATEGORY[intent]
        mode = _INTENT_TO_MODE[intent]
        path = _BUNDLED_ROOT / category / "en" / mode / "system.md"
        assert path.exists(), f"{intent.value} route target is missing: {path}"

    def test_cr02_targets_all_have_governance_decisions(self) -> None:
        governed = (
            set(_INTENT_TO_MODE) | set(_CONTEXT_MODE_REQUIRED_INTENTS) | set(_NON_ROUTEABLE_INTENTS)
        )
        assert governed >= _CR02_TARGETS

    def test_known_cr02_remaps_use_existing_templates(self) -> None:
        assert _INTENT_TO_MODE[LLMIntent.ANALYSE] == "review"
        assert _INTENT_TO_MODE[LLMIntent.PLAN] == "outline"

    @pytest.mark.parametrize("intent", sorted(_CONTEXT_MODE_REQUIRED_INTENTS, key=str))
    async def test_context_mode_required_intents_fail_without_mode(
        self,
        composer: PromptComposer,
        intent: LLMIntent,
    ) -> None:
        with pytest.raises(PromptRouteNotConfiguredError, match=intent.value):
            await composer.build(intent, PromptContext(language="en"))

    async def test_context_mode_required_intent_uses_supplied_mode(self) -> None:
        fake_registry = FakePromptRegistry()
        composer = PromptComposer(fake_registry)  # type: ignore[arg-type]

        await composer.build(
            LLMIntent.EXTRACT,
            PromptContext(language="en", mode="preferences"),
        )

        assert fake_registry.calls[-1]["category"] == "analysis"
        assert fake_registry.calls[-1]["mode"] == "preferences"

    async def test_kb_create_allows_only_documented_aggregate_modes(self) -> None:
        fake_registry = FakePromptRegistry()
        composer = PromptComposer(fake_registry)  # type: ignore[arg-type]

        with pytest.raises(PromptRouteNotConfiguredError, match="unsupported_mode"):
            await composer.build(
                LLMIntent.KB_CREATE,
                PromptContext(language="en", mode="unsupported_mode"),
            )

        assert fake_registry.calls == []

    @pytest.mark.parametrize("intent", sorted(_NON_ROUTEABLE_INTENTS, key=str))
    async def test_non_routeable_intents_fail_before_registry_lookup(
        self,
        fake_registry: FakePromptRegistry,
        intent: LLMIntent,
    ) -> None:
        composer = PromptComposer(fake_registry)  # type: ignore[arg-type]

        with pytest.raises(PromptRouteNotConfiguredError, match=intent.value):
            await composer.build(intent, PromptContext(language="en"))

        assert fake_registry.calls == []
