"""Tests for narrare_core.settings — CoreSettings model and cached accessor.

ADR-071: CoreSettings centralises all env-var-backed Core configuration.
These tests verify construction, defaults, env-var mapping (including the
``NARRARE_*`` aliases), bool coercion, and the cached ``get_core_settings()``
accessor behaviour.
"""

from __future__ import annotations

import pytest

from narrare_core.settings import CoreSettings, get_core_settings


class TestCoreSettingsDefaults:
    """Default values when no env vars are set."""

    def test_defaults_when_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
            "ZAI_API_KEY",
            "OPENAI_BASE_URL",
            "ANTHROPIC_BASE_URL",
            "NARRARE_ENCRYPTION_KEY",
            "NARRARE_LLM_TRANSPORT_MAX_RETRIES",
            "DEFAULT_EMBEDDING_MODEL",
            "NARRARE_E2E_TEST",
            "OLLAMA_BASE_URL",
        ]:
            monkeypatch.delenv(var, raising=False)

        settings = CoreSettings()
        assert settings.openai_api_key is None
        assert settings.anthropic_api_key is None
        assert settings.google_api_key is None
        assert settings.gemini_api_key is None
        assert settings.groq_api_key is None
        assert settings.openrouter_api_key is None
        assert settings.zai_api_key is None
        assert settings.openai_base_url is None
        assert settings.anthropic_base_url is None
        assert settings.encryption_key == ""
        assert settings.llm_transport_max_retries == 2
        assert settings.default_embedding_model == "text-embedding-3-small"
        assert settings.e2e_test is False
        assert settings.ollama_base_url == "http://localhost:11434"


class TestCoreSettingsEnvMapping:
    """Each field reads the correct environment variable."""

    def test_openai_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        assert CoreSettings().openai_api_key == "sk-openai"

    def test_anthropic_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        assert CoreSettings().anthropic_api_key == "sk-ant"

    def test_google_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
        assert CoreSettings().google_api_key == "g-key"

    def test_gemini_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
        assert CoreSettings().gemini_api_key == "gem-key"

    def test_groq_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gsk-key")
        assert CoreSettings().groq_api_key == "gsk-key"

    def test_openrouter_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        assert CoreSettings().openrouter_api_key == "or-key"

    def test_zai_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZAI_API_KEY", "zai-key")
        assert CoreSettings().zai_api_key == "zai-key"

    def test_ollama_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://myhost:9999")
        assert CoreSettings().ollama_base_url == "http://myhost:9999"

    def test_openai_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.openai.com")
        assert CoreSettings().openai_base_url == "https://proxy.openai.com"

    def test_anthropic_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.anthropic.com")
        assert CoreSettings().anthropic_base_url == "https://proxy.anthropic.com"


class TestCoreSettingsAliases:
    """NARRARE_* env vars are read via aliases (not default name uppercasing)."""

    def test_encryption_key_from_narrare_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("NARRARE_ENCRYPTION_KEY", "fernet-key-value")
        assert CoreSettings().encryption_key == "fernet-key-value"

    def test_transport_retries_from_narrare_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLM_TRANSPORT_MAX_RETRIES", raising=False)
        monkeypatch.setenv("NARRARE_LLM_TRANSPORT_MAX_RETRIES", "5")
        assert CoreSettings().llm_transport_max_retries == 5

    def test_e2e_test_from_narrare_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("E2E_TEST", raising=False)
        monkeypatch.setenv("NARRARE_E2E_TEST", "1")
        assert CoreSettings().e2e_test is True

    def test_default_embedding_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEFAULT_EMBEDDING_MODEL", "custom-embed-model")
        assert CoreSettings().default_embedding_model == "custom-embed-model"


class TestCoreSettingsBoolCoercion:
    """e2e_test coerces common truthy/falsy string values."""

    @pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on"])
    def test_truthy_values(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("NARRARE_E2E_TEST", value)
        assert CoreSettings().e2e_test is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_falsy_values(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("NARRARE_E2E_TEST", value)
        assert CoreSettings().e2e_test is False

    def test_unset_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NARRARE_E2E_TEST", raising=False)
        assert CoreSettings().e2e_test is False


class TestCoreSettingsConstructionByName:
    """CoreSettings can be constructed with field names (populate_by_name)."""

    def test_construct_with_field_names(self) -> None:
        settings = CoreSettings(
            openai_api_key="test-key",
            encryption_key="test-encryption-key",
            e2e_test=True,
            llm_transport_max_retries=7,
        )
        assert settings.openai_api_key == "test-key"
        assert settings.encryption_key == "test-encryption-key"
        assert settings.e2e_test is True
        assert settings.llm_transport_max_retries == 7


class TestGetCoreSettingsAccessor:
    """get_core_settings() is a cached singleton accessor."""

    def test_returns_core_settings_instance(self) -> None:
        assert isinstance(get_core_settings(), CoreSettings)

    def test_cached_singleton_returns_same_instance(self) -> None:
        first = get_core_settings()
        second = get_core_settings()
        assert first is second

    def test_cache_clear_yields_new_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "first-key")
        first = get_core_settings()
        assert first.openai_api_key == "first-key"

        # Change env + clear cache -> next call reconstructs
        monkeypatch.setenv("OPENAI_API_KEY", "second-key")
        get_core_settings.cache_clear()
        second = get_core_settings()
        assert second.openai_api_key == "second-key"
        assert first is not second

    def test_extra_env_vars_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """extra='ignore' — unknown env vars don't cause errors."""
        monkeypatch.setenv("NARRARE_UNKNOWN_CORE_VAR", "whatever")
        # Should not raise
        settings = CoreSettings()
        assert settings is not None
