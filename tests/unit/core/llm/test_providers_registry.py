"""Tests for llm/_providers/registry.py — provider registration and inference."""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.llm._providers.registry import (
    available,
    get,
    infer_provider,
    register,
    register_model,
)


class TestRegisterAndGet:
    @pytest.fixture(autouse=True)
    def _clear_e2e_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure NARRARE_E2E_TEST is not set during registry tests.

        ``NARRARE_E2E_TEST`` may leak from a developer shell or an e2e-mode
        invocation (the justfile no longer auto-loads ``.env``). When this
        variable is set, ``get()`` in ``registry.py`` returns
        ``_test_model_factory`` instead of the registered factory, breaking
        tests that exercise real factory registration and credential passing.
        """
        monkeypatch.delenv("NARRARE_E2E_TEST", raising=False)

    def test_register_and_retrieve_factory(self) -> None:
        def my_factory(model_id: str) -> object:
            return f"model:{model_id}"

        register("__test_provider", my_factory)  # pyright: ignore[reportArgumentType]

        result = get("__test_provider")
        assert result("gpt-4o") == "model:gpt-4o"

    def test_get_raises_for_unknown_provider(self) -> None:
        with pytest.raises(KeyError, match="Unknown provider"):
            get("__nonexistent_provider_xyz")

    def test_available_returns_sorted_names(self) -> None:
        names = available()
        assert isinstance(names, list)
        assert names == sorted(names)

    def test_all_expected_providers_registered(self) -> None:
        """All providers defined in _providers/__init__.py must be registered."""
        providers = available()
        for expected in ["anthropic", "openai", "zai", "ollama", "google", "groq", "openrouter"]:
            assert expected in providers, f"Provider '{expected}' not registered"


class TestRegisterModel:
    def test_explicit_model_overrides_prefix_inference(self) -> None:
        """Explicit model registration takes priority over prefix matching."""
        register_model("__test-custom-model", "anthropic")
        assert infer_provider("__test-custom-model") == "anthropic"

    def test_explicit_model_is_case_insensitive(self) -> None:
        """Model registration normalizes to lowercase."""
        register_model("__Test-Model-UPPER", "zai")
        # Exact match (lowercased)
        assert infer_provider("__test-model-upper") == "zai"
        # Original case also works (infer_provider lowercases the lookup)
        assert infer_provider("__Test-Model-UPPER") == "zai"

    def test_explicit_model_overrides_default_fallback(self) -> None:
        """Explicit registration can route unknown-prefix models to a provider."""
        register_model("__totally-unknown-model", "google")
        assert infer_provider("__totally-unknown-model") == "google"

    def test_prefix_matching_still_works_without_explicit(self) -> None:
        """Models without explicit registration still use prefix matching."""
        assert infer_provider("claude-some-new-future-model") == "anthropic"

    def test_register_model_can_override_previous(self) -> None:
        """Last registration wins for the same model ID."""
        register_model("__override-test", "openai")
        register_model("__override-test", "anthropic")
        assert infer_provider("__override-test") == "anthropic"


class TestInferProvider:
    @pytest.mark.parametrize(
        ("model_id", "expected"),
        [
            ("claude-sonnet-4-5-20251020", "anthropic"),
            ("claude-opus-4-5-20251101", "anthropic"),
            ("Claude-3-Haiku", "anthropic"),
            ("gpt-4o", "openai"),
            ("gpt-3.5-turbo", "openai"),
            ("o1-preview", "openai"),
            ("o3-mini", "openai"),
            ("text-embedding-3-small", "openai"),
            ("glm-z1-32b", "zai"),
            ("chatglm-4", "zai"),
            ("GLM-4-Flash", "zai"),
            ("gemini-2.0-flash", "google"),
            ("gemini-1.5-pro", "google"),
            ("ollama/llama3.2", "ollama"),
            ("mixtral-8x7b", "groq"),
            ("llama-3.3-70b", "ollama"),  # "llama" without "/" matches ollama prefix
            ("openrouter/some-model", "openrouter"),
        ],
    )
    def test_infers_correct_provider(self, model_id: str, expected: str) -> None:
        assert infer_provider(model_id) == expected

    def test_unknown_model_defaults_to_openai(self) -> None:
        assert infer_provider("some-unknown-model-id") == "openai"

    def test_llama_without_prefix_is_ollama(self) -> None:
        # "llama" prefix routes to ollama
        assert infer_provider("llama3.2") == "ollama"

    def test_ollama_prefix_overrides_llama(self) -> None:
        # "ollama/llama3" matches "ollama/" prefix before "llama" prefix
        assert infer_provider("ollama/llama3") == "ollama"


class TestProviderFactoryCredentials:
    """Test that provider factories accept api_key and base_url kwargs."""

    @pytest.fixture(autouse=True)
    def _clear_e2e_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure NARRARE_E2E_TEST is not set during credential tests.

        See ``TestRegisterAndGet._clear_e2e_env`` for rationale.
        """
        monkeypatch.delenv("NARRARE_E2E_TEST", raising=False)

    def test_factory_accepts_api_key_kwarg(self) -> None:
        """Registered factories accept api_key keyword argument."""
        captured_kwargs: dict[str, object] = {}

        def factory(
            model_id: str, *, api_key: str | None = None, base_url: str | None = None
        ) -> object:
            captured_kwargs["api_key"] = api_key
            captured_kwargs["base_url"] = base_url
            return f"model:{model_id}"

        register("__test_cred_factory", factory)  # pyright: ignore[reportArgumentType]
        result = get("__test_cred_factory")
        result("gpt-4o", api_key="sk-explicit-key")

        assert captured_kwargs["api_key"] == "sk-explicit-key"
        assert captured_kwargs["base_url"] is None

    def test_factory_accepts_base_url_kwarg(self) -> None:
        """Registered factories accept base_url keyword argument."""
        captured_kwargs: dict[str, object] = {}

        def factory(
            model_id: str, *, api_key: str | None = None, base_url: str | None = None
        ) -> object:
            captured_kwargs["api_key"] = api_key
            captured_kwargs["base_url"] = base_url
            return f"model:{model_id}"

        register("__test_url_factory", factory)  # pyright: ignore[reportArgumentType]
        result = get("__test_url_factory")
        result("gpt-4o", base_url="https://proxy.example.com/v1")

        assert captured_kwargs["api_key"] is None
        assert captured_kwargs["base_url"] == "https://proxy.example.com/v1"

    def test_factory_without_credentials_uses_none(self) -> None:
        """Factory called without credentials → api_key=None, base_url=None (env var fallback)."""
        captured_kwargs: dict[str, object] = {}

        def factory(
            model_id: str, *, api_key: str | None = None, base_url: str | None = None
        ) -> object:
            captured_kwargs["api_key"] = api_key
            captured_kwargs["base_url"] = base_url
            return f"model:{model_id}"

        register("__test_no_cred_factory", factory)  # pyright: ignore[reportArgumentType]
        result = get("__test_no_cred_factory")
        result("gpt-4o")

        assert captured_kwargs["api_key"] is None
        assert captured_kwargs["base_url"] is None

    @pytest.mark.parametrize(
        "provider_name",
        ["anthropic", "openai", "google", "groq", "openrouter", "zai", "ollama"],
    )
    def test_all_registered_providers_accept_credentials(
        self,
        provider_name: str,
    ) -> None:
        """All registered providers accept api_key and base_url kwargs without error."""
        factory = get(provider_name)
        # This should not raise — the factory protocol requires these kwargs
        # We don't call the factory (would need real credentials), just verify
        # it accepts the kwargs by inspecting its signature
        import inspect

        sig = inspect.signature(factory)
        params = sig.parameters
        assert "api_key" in params, f"{provider_name} factory missing api_key param"
        assert "base_url" in params, f"{provider_name} factory missing base_url param"


class TestE2ETestMode:
    """When NARRARE_E2E_TEST is set, get() returns a TestModel factory.

    This overrides all registered providers with pydantic-ai's TestModel so
    no real LLM calls are made during E2E tests (prevents 401 from unset keys).
    """

    @pytest.fixture(autouse=True)
    def _set_e2e_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NARRARE_E2E_TEST", "1")

    def test_e2e_env_returns_test_model_factory(self) -> None:
        factory = get("openai")
        model = factory("gpt-4o")
        assert isinstance(model, TestModel)

    def test_e2e_factory_ignores_credentials(self) -> None:
        """The E2E factory ignores api_key/base_url — always returns TestModel."""
        factory = get("anthropic")
        model = factory("claude-sonnet-4-5", api_key="sk-test", base_url="https://proxy")
        assert isinstance(model, TestModel)

    @pytest.mark.parametrize(
        "provider_name",
        ["anthropic", "openai", "google", "groq", "openrouter", "zai", "ollama"],
    )
    def test_e2e_env_works_for_all_providers(self, provider_name: str) -> None:
        factory = get(provider_name)
        assert isinstance(factory("test-model"), TestModel)
