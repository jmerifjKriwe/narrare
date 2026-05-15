"""Tests for memory/mem0_client.py — _default_memory_model()."""

from __future__ import annotations

from narrare_core.memory.mem0_client import _default_memory_model


class TestDefaultMemoryModel:
    """Known providers return correct model; unknown returns fallback."""

    def test_anthropic_returns_haiku(self) -> None:
        assert _default_memory_model("anthropic") == "claude-haiku-4-20250414"

    def test_openai_returns_nano(self) -> None:
        assert _default_memory_model("openai") == "gpt-4.1-nano"

    def test_ollama_returns_llama(self) -> None:
        assert _default_memory_model("ollama") == "llama3.2:3b"

    def test_zai_returns_glm(self) -> None:
        assert _default_memory_model("zai") == "glm-4-flash"

    def test_unknown_provider_returns_fallback(self) -> None:
        assert _default_memory_model("unknown_provider") == "gpt-4.1-nano"

    def test_empty_string_returns_fallback(self) -> None:
        assert _default_memory_model("") == "gpt-4.1-nano"
