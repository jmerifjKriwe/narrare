"""Tests for llm/_providers/registry.py — provider registration and inference."""

from __future__ import annotations

import pytest

from narrare_core.llm._providers.registry import (
    available,
    get,
    infer_provider,
    register,
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
            ("llama-3.3-70b", "ollama"),  # "llama" without "/" matches ollama rule first
            ("openrouter/some-model", "openrouter"),
        ],
    )
    def test_infers_correct_provider(self, model_id: str, expected: str) -> None:
        assert infer_provider(model_id) == expected

    def test_unknown_model_defaults_to_openai(self) -> None:
        assert infer_provider("some-unknown-model-id") == "openai"

    def test_llama_without_prefix_is_ollama(self) -> None:
        # "llama" without "/" prefix matches the ollama rule first (line 91)
        assert infer_provider("llama3.2") == "ollama"

    def test_ollama_prefix_overrides_llama(self) -> None:
        # "ollama/llama3" should be ollama, not groq
        assert infer_provider("ollama/llama3") == "ollama"
