"""Tests for llm/_model_settings.py — build_runtime_model_settings.

Covers:
- Intent-aware thinking policy (universal — no provider branching):
  KB/extraction intents → ``thinking: "low"``, analysis → ``"medium"``,
  creative/chat intents → key omitted
- Provider-universality: the intent-derived key is set for every provider;
  providers without thinking support drop it later at request time
  (pydantic-ai ``supports_thinking`` profile gate)
- Regression: the former ``provider_name == "zai"`` branch is gone — the
  provider name alone no longer triggers a thinking default
- max_tokens forwarding (ADR-045) combined with the thinking level
- Empty-settings → ``None`` contract preserved
"""

from __future__ import annotations

from pydantic_ai.usage import UsageLimits

from narrare_core.llm import CacheSettings, ResolvedModelConfig
from narrare_core.llm._model_settings import build_runtime_model_settings
from narrare_core.llm.intents import LLMIntent


class TestIntentDrivenThinking:
    """Thinking levels come from the intent, not the provider."""

    def test_zai_config_with_kb_extract_intent_gets_thinking_low(self) -> None:
        config = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        settings = build_runtime_model_settings(config, None, intent=LLMIntent.KB_EXTRACT)
        assert settings is not None
        assert settings.get("thinking") == "low"

    def test_openai_config_with_kb_extract_intent_gets_thinking_low(self) -> None:
        """Provider-universal: the key is set for every provider; pydantic-ai's
        ``supports_thinking`` profile gate drops it at request time where the
        model cannot think."""
        config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")
        settings = build_runtime_model_settings(config, None, intent=LLMIntent.KB_EXTRACT)
        assert settings == {"thinking": "low"}

    def test_analyse_intent_gets_thinking_medium(self) -> None:
        config = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        settings = build_runtime_model_settings(config, None, intent=LLMIntent.ANALYSE)
        assert settings is not None
        assert settings.get("thinking") == "medium"

    def test_write_intent_omits_thinking_key(self) -> None:
        config = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        settings = build_runtime_model_settings(config, None, intent=LLMIntent.WRITE)
        assert settings is None  # zai has no cache settings — nothing else to send

    def test_chat_intent_omits_thinking_key(self) -> None:
        config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")
        settings = build_runtime_model_settings(config, None, intent=LLMIntent.CHAT)
        assert settings is None

    def test_no_intent_sets_no_thinking(self) -> None:
        """``intent=None`` (generic path) → no thinking key — provider default."""
        config = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        settings = build_runtime_model_settings(config, None, intent=None)
        assert settings is None

    def test_zai_config_without_intent_has_no_thinking(self) -> None:
        """Regression: the former ``provider_name == "zai"`` branch is deleted —
        the provider name alone must no longer trigger a thinking default."""
        config = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        settings = build_runtime_model_settings(config, None)
        assert settings is None


class TestThinkingCombinedWithOutputTokenCap:
    """The thinking level and the ADR-045 max_tokens cap coexist."""

    def test_kb_extract_intent_with_output_token_cap(self) -> None:
        config = ResolvedModelConfig(provider_name="zai", model_id="glm-5.3-flash")
        limits = UsageLimits(output_tokens_limit=8000)
        settings = build_runtime_model_settings(config, limits, intent=LLMIntent.KB_EXTRACT)
        assert settings == {"thinking": "low", "max_tokens": 8000}

    def test_analyse_intent_with_output_token_cap_and_cache(self) -> None:
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5",
            cache=CacheSettings(),
        )
        limits = UsageLimits(output_tokens_limit=1000)
        settings = build_runtime_model_settings(config, limits, intent=LLMIntent.ANALYSE)
        assert settings == {"cache_control": True, "max_tokens": 1000, "thinking": "medium"}


class TestEmptySettingsContract:
    """Existing behaviour preserved: no settings to send → ``None``."""

    def test_openai_no_settings_no_intent_returns_none(self) -> None:
        config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")
        settings = build_runtime_model_settings(config, None)
        assert settings is None

    def test_anthropic_cache_only_settings_preserved(self) -> None:
        config = ResolvedModelConfig(
            provider_name="anthropic", model_id="claude-sonnet-4-5", cache=CacheSettings()
        )
        settings = build_runtime_model_settings(config, None)
        assert settings == {"cache_control": True}
        assert settings is not None
        assert "thinking" not in settings
