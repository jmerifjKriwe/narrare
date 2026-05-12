"""Tests for llm/_providers/registry.py — provider registration and inference."""

from __future__ import annotations

import pytest

from narrare_core.llm._providers.registry import (
    available,
    get,
    infer_provider,
    register,
    register_model,
)


class TestRegisterAndGet:
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
