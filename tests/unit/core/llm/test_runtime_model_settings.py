"""Tests for llm/_model_settings.py — build_runtime_model_settings.

Covers:
- Z.AI thinking default: unified pydantic-ai ``thinking`` setting ("low")
- Provider isolation: non-zai configs carry no ``thinking`` key
- max_tokens forwarding (ADR-045) combined with the thinking default
- Existing empty-settings → ``None`` contract preserved
"""

from __future__ import annotations

from pydantic_ai.usage import UsageLimits

from narrare_core.llm import CacheSettings, ResolvedModelConfig
from narrare_core.llm._model_settings import build_runtime_model_settings


class TestZaiThinkingDefault:
    """Z.AI configs get the unified ``thinking`` default ("low").

    Root cause: GLM models (notably glm-5.3-flash) think extensively by
    default — ~50k reasoning tokens on a 6.3k-token extraction prompt
    (~7 min). ``reasoning_effort: "low"`` completes the same task in ~22s /
    872 completion tokens (verified via direct API probe). pydantic-ai's
    unified ``ModelSettings['thinking']`` maps to ``reasoning_effort`` for
    OpenAI-compatible endpoints.
    """

    def test_zai_config_gets_thinking_low(self) -> None:
        config = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        settings = build_runtime_model_settings(config, None)
        assert settings is not None
        assert "thinking" in settings
        assert settings["thinking"] == "low"

    def test_zai_thinking_combined_with_output_token_cap(self) -> None:
        """thinking default and the ADR-045 max_tokens cap coexist."""
        config = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        limits = UsageLimits(output_tokens_limit=8000)
        settings = build_runtime_model_settings(config, limits)
        assert settings == {"thinking": "low", "max_tokens": 8000}


class TestNonZaiConfigsHaveNoThinking:
    """The thinking default is provider-scoped — no leakage to other providers."""

    def test_anthropic_config_has_no_thinking(self) -> None:
        config = ResolvedModelConfig(
            provider_name="anthropic", model_id="claude-sonnet-4-5", cache=CacheSettings()
        )
        settings = build_runtime_model_settings(config, None)
        assert settings == {"cache_control": True}
        assert settings is not None
        assert "thinking" not in settings

    def test_openai_config_has_no_thinking(self) -> None:
        config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")
        limits = UsageLimits(output_tokens_limit=1000)
        settings = build_runtime_model_settings(config, limits)
        assert settings == {"max_tokens": 1000}
        assert settings is not None
        assert "thinking" not in settings


class TestEmptySettingsContract:
    """Existing behaviour: no settings to send → ``None``."""

    def test_openai_no_settings_returns_none(self) -> None:
        config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")
        settings = build_runtime_model_settings(config, None)
        assert settings is None
