"""Tests for llm/_providers/others.py — Google, Groq, and OpenRouter factories.

Exercises the actual factory bodies to verify:
- Correct pydantic-ai Model types returned (GoogleModel, GroqModel, OpenAIChatModel)
- API key routing (explicit vs env-var fallback)
- Default and custom base URLs
- Model-ID prefix stripping ("openrouter/" prefix removed)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIChatModel

from narrare_core.llm._providers.others import _make_google, _make_groq, _make_openrouter

if TYPE_CHECKING:
    import pytest


class TestMakeGoogle:
    """``_make_google`` creates ``GoogleModel`` with credential routing."""

    def test_with_api_key_returns_google_model(self) -> None:
        model = _make_google("gemini-2.0-flash", api_key="google-key")
        assert isinstance(model, GoogleModel)
        assert model.model_name == "gemini-2.0-flash"

    def test_env_var_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_API_KEY", "env-google-key")
        model = _make_google("gemini-1.5-pro")
        assert isinstance(model, GoogleModel)
        assert model.model_name == "gemini-1.5-pro"

    def test_with_gemini_env_var_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GEMINI_API_KEY is also accepted as env-var fallback."""
        monkeypatch.setenv("GEMINI_API_KEY", "gemini-env-key")
        model = _make_google("gemini-2.0-flash")
        assert isinstance(model, GoogleModel)

    def test_ignores_base_url(self) -> None:
        """base_url is accepted but Google uses its official endpoint."""
        model = _make_google("gemini-2.0-flash", api_key="k", base_url="https://ignored")
        assert isinstance(model, GoogleModel)


class TestMakeGroq:
    """``_make_groq`` creates ``GroqModel`` with credential routing."""

    def test_with_api_key_returns_groq_model(self) -> None:
        model = _make_groq("mixtral-8x7b-32768", api_key="gsk-test")
        assert isinstance(model, GroqModel)
        assert model.model_name == "mixtral-8x7b-32768"

    def test_env_var_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "env-groq-key")
        model = _make_groq("llama-3.3-70b-versatile")
        assert isinstance(model, GroqModel)
        assert model.model_name == "llama-3.3-70b-versatile"

    def test_ignores_base_url(self) -> None:
        model = _make_groq("mixtral-8x7b", api_key="k", base_url="https://ignored")
        assert isinstance(model, GroqModel)


class TestMakeOpenRouter:
    """``_make_openrouter`` creates ``OpenAIChatModel`` via OpenRouter endpoint."""

    def test_with_api_key_returns_model(self) -> None:
        model = _make_openrouter("meta/llama", api_key="or-key")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "meta/llama"

    def test_default_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-key")
        model = _make_openrouter("meta/llama")
        assert model.base_url == "https://openrouter.ai/api/v1/"

    def test_strips_openrouter_prefix(self) -> None:
        model = _make_openrouter("openrouter/meta/llama", api_key="k")
        assert model.model_name == "meta/llama"

    def test_custom_base_url(self) -> None:
        model = _make_openrouter("meta/llama", api_key="k", base_url="https://custom.or/v1")
        assert model.base_url == "https://custom.or/v1/"

    def test_env_var_key_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "env-or-key")
        model = _make_openrouter("meta/llama")
        assert isinstance(model, OpenAIChatModel)
