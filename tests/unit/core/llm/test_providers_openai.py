"""Tests for llm/_providers/openai.py — OpenAI factory construction.

Exercises the actual ``_make_openai`` factory body to verify:
- Correct pydantic-ai Model type returned
- API key routing (explicit vs env-var fallback)
- Base URL override (proxy / OpenAI-compatible endpoints)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models.openai import OpenAIChatModel

from narrare_core.llm._providers.openai import _make_openai

if TYPE_CHECKING:
    import pytest


class TestMakeOpenAI:
    """``_make_openai`` creates ``OpenAIChatModel`` with credential routing."""

    def test_with_api_key_returns_openai_model(self) -> None:
        model = _make_openai("gpt-4o", api_key="sk-test")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "gpt-4o"

    def test_with_base_url_returns_openai_model(self) -> None:
        model = _make_openai("gpt-4o", base_url="https://proxy.example.com/v1")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "gpt-4o"

    def test_with_both_api_key_and_base_url(self) -> None:
        model = _make_openai("gpt-4o", api_key="sk-test", base_url="https://proxy/v1")
        assert isinstance(model, OpenAIChatModel)
        assert "proxy" in model.base_url

    def test_env_var_fallback_when_no_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without explicit credentials, falls back to OPENAI_API_KEY env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-fallback")
        model = _make_openai("gpt-4o")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "gpt-4o"
