"""Tests für CacheSettings und provider-specific ModelSettings (ADR-016 Phase 1).

Covers:
- CacheSettings defaults
- build_model_settings for all provider types
- ResolvedModelConfig.cache field
- ModelRegistry.get_cache_settings() integration
"""

from __future__ import annotations

from narrare_core.llm import CacheSettings, ResolvedModelConfig
from narrare_core.llm._providers.cache_settings import build_model_settings

# ---------------------------------------------------------------------------
# CacheSettings defaults
# ---------------------------------------------------------------------------


class TestCacheSettings:
    """CacheSettings dataclass defaults."""

    def test_defaults(self) -> None:
        """CacheSettings has expected defaults."""
        cs = CacheSettings()
        assert cs.enabled is True
        assert cs.ttl_seconds == 300
        assert cs.max_cache_points == 4

    def test_frozen(self) -> None:
        """CacheSettings is frozen (immutable)."""
        cs = CacheSettings()
        try:
            cs.enabled = False  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass  # expected

    def test_custom_values(self) -> None:
        """CacheSettings accepts custom values."""
        cs = CacheSettings(enabled=False, ttl_seconds=600, max_cache_points=2)
        assert cs.enabled is False
        assert cs.ttl_seconds == 600
        assert cs.max_cache_points == 2


# ---------------------------------------------------------------------------
# build_model_settings — provider mapping
# ---------------------------------------------------------------------------


class TestBuildModelSettings:
    """build_model_settings returns provider-specific ModelSettings kwargs."""

    def test_cache_none_returns_empty(self) -> None:
        """cache=None → empty dict."""
        assert build_model_settings("anthropic", None) == {}

    def test_cache_disabled_returns_empty(self) -> None:
        """cache.enabled=False → empty dict."""
        cs = CacheSettings(enabled=False)
        assert build_model_settings("anthropic", cs) == {}

    def test_anthropic_returns_cache_control(self) -> None:
        """Anthropic provider → {"cache_control": True}."""
        cs = CacheSettings()
        result = build_model_settings("anthropic", cs)
        assert result == {"cache_control": True}

    def test_openai_returns_empty(self) -> None:
        """OpenAI provider → {} (automatic server-side caching)."""
        cs = CacheSettings()
        assert build_model_settings("openai", cs) == {}

    def test_zai_returns_empty(self) -> None:
        """Z.AI provider → {} (automatic server-side caching)."""
        cs = CacheSettings()
        assert build_model_settings("zai", cs) == {}

    def test_groq_returns_empty(self) -> None:
        """Groq provider → {} (automatic server-side caching)."""
        cs = CacheSettings()
        assert build_model_settings("groq", cs) == {}

    def test_ollama_returns_empty(self) -> None:
        """Ollama provider → {} (no caching support)."""
        cs = CacheSettings()
        assert build_model_settings("ollama", cs) == {}

    def test_google_returns_empty(self) -> None:
        """Google provider → {} (future: cached_contents API)."""
        cs = CacheSettings()
        assert build_model_settings("google", cs) == {}

    def test_openrouter_returns_empty(self) -> None:
        """OpenRouter provider → {} (automatic server-side caching)."""
        cs = CacheSettings()
        assert build_model_settings("openrouter", cs) == {}

    def test_unknown_provider_returns_empty(self) -> None:
        """Unknown provider → {} (safe fallback)."""
        cs = CacheSettings()
        assert build_model_settings("some_new_provider", cs) == {}


# ---------------------------------------------------------------------------
# ResolvedModelConfig.cache field
# ---------------------------------------------------------------------------


class TestResolvedModelConfigCache:
    """ResolvedModelConfig accepts cache field."""

    def test_default_cache_is_none(self) -> None:
        """Default cache is None (no caching configured)."""
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        assert config.cache is None

    def test_accepts_cache_settings(self) -> None:
        """cache field accepts CacheSettings instance."""
        cs = CacheSettings(ttl_seconds=600)
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            cache=cs,
        )
        assert config.cache is not None
        assert config.cache.ttl_seconds == 600

    def test_backward_compatible_without_cache(self) -> None:
        """Existing code without cache still works."""
        config = ResolvedModelConfig(
            provider_name="openai",
            model_id="gpt-4o",
            temperature=0.5,
        )
        assert config.provider_name == "openai"
        assert config.cache is None


# ---------------------------------------------------------------------------
# ModelRegistry.get_cache_settings() integration
# ---------------------------------------------------------------------------


class TestModelRegistryGetCacheSettings:
    """ModelRegistry.get_cache_settings delegates to build_model_settings."""

    def test_no_cache_returns_empty(self) -> None:
        """Config without cache → empty dict."""
        from narrare_core.llm.gateway import ModelRegistry

        registry = ModelRegistry()
        config = ResolvedModelConfig(
            provider_name="openai",
            model_id="gpt-4o",
        )
        assert registry.get_cache_settings(config) == {}

    def test_anthropic_with_cache_returns_cache_control(self) -> None:
        """Anthropic config with CacheSettings → {"cache_control": True}."""
        from narrare_core.llm.gateway import ModelRegistry

        registry = ModelRegistry()
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            cache=CacheSettings(),
        )
        result = registry.get_cache_settings(config)
        assert result == {"cache_control": True}

    def test_synchronous_call(self) -> None:
        """get_cache_settings is synchronous (not async)."""
        from narrare_core.llm.gateway import ModelRegistry

        registry = ModelRegistry()
        config = ResolvedModelConfig(
            provider_name="openai",
            model_id="gpt-4o",
            cache=CacheSettings(),
        )
        # Should not raise — synchronous call
        result = registry.get_cache_settings(config)
        assert isinstance(result, dict)
