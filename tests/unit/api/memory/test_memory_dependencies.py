"""Tests for memory/dependencies.py provider detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from narrare.memory.dependencies import _detect_provider_from_env


class TestDetectProviderFromEnv:
    """Tests for the _detect_provider_from_env helper."""

    def test_openai_env_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.openai.com")

        result = _detect_provider_from_env()

        assert result is not None
        assert result.provider == "openai"
        assert result.api_key == "sk-test"
        assert result.base_url == "https://custom.openai.com"

    def test_anthropic_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        result = _detect_provider_from_env()

        assert result is not None
        assert result.provider == "anthropic"
        assert result.api_key == "sk-ant-test"

    def test_no_credentials_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        result = _detect_provider_from_env()

        assert result is None

    def test_openai_priority_over_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        result = _detect_provider_from_env()

        assert result is not None
        assert result.provider == "openai"

    def test_base_url_none_when_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

        result = _detect_provider_from_env()

        assert result is not None
        assert result.base_url is None

    def test_anthropic_base_url_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://custom.anthropic.com")

        result = _detect_provider_from_env()

        assert result is not None
        assert result.provider == "anthropic"
        assert result.base_url == "https://custom.anthropic.com"
