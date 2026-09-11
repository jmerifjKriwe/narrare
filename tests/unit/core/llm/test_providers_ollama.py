"""Tests for llm/_providers/ollama.py — Ollama factory construction.

Exercises the actual ``_make_ollama`` factory body to verify:
- Correct pydantic-ai Model type returned
- Default base URL (localhost:11434)
- Custom base URL with trailing-slash normalization
- Env-var base URL override (OLLAMA_BASE_URL)
- Model-ID prefix stripping ("ollama/" prefix removed)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

from narrare_core.llm._providers.ollama import _make_ollama
from narrare_core.llm._schema_transformer import NarrareOpenAICompatJsonSchemaTransformer

if TYPE_CHECKING:
    import pytest


class TestMakeOllama:
    """``_make_ollama`` creates ``OpenAIChatModel`` via Ollama endpoint."""

    def test_default_url_localhost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        model = _make_ollama("llama3")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "llama3"
        assert model.base_url == "http://localhost:11434/v1/"

    def test_strips_ollama_prefix(self) -> None:
        """Model IDs with 'ollama/' prefix have it stripped."""
        model = _make_ollama("ollama/llama3.2")
        assert model.model_name == "llama3.2"

    def test_custom_base_url_strips_trailing_slash(self) -> None:
        """Trailing slash in base_url is stripped before appending '/v1'."""
        model = _make_ollama("llama3", base_url="http://myhost:8080/")
        assert model.base_url == "http://myhost:8080/v1/"

    def test_env_var_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-host:1234")
        model = _make_ollama("mistral")
        assert model.base_url == "http://env-host:1234/v1/"
        assert model.model_name == "mistral"


class TestOllamaProviderFacts:
    """Ollama models route through pydantic-ai's native ``OllamaProvider``.

    The native provider imports upstream-maintained capability facts (strict
    tool definitions unsupported, ``reasoning`` thinking field, native JSON
    schema output); the shared profile hook swaps in the universal inlining
    transformer on top.
    """

    def test_provider_is_native_ollama_provider(self) -> None:
        model = _make_ollama("llama3")
        assert isinstance(model.provider, OllamaProvider)

    def test_profile_carries_inlining_transformer(self) -> None:
        model = _make_ollama("llama3")
        assert model.profile.get("json_schema_transformer") is (
            NarrareOpenAICompatJsonSchemaTransformer
        )

    def test_upstream_capability_facts_retained(self) -> None:
        model = _make_ollama("llama3")
        assert model.profile.get("openai_supports_strict_tool_definition") is False
        assert model.profile.get("openai_chat_thinking_field") == "reasoning"
