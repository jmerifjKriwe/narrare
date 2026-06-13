"""Tests for narrare_core.memory.availability — is_mem0_available and detect_provider_from_env."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

from narrare_core.memory.availability import (
    ProviderEnvConfig,
    detect_provider_from_env,
    is_mem0_available,
)

# ---------------------------------------------------------------------------
# is_mem0_available
# ---------------------------------------------------------------------------


class TestIsMem0Available:
    """Tests for is_mem0_available package detection."""

    def test_returns_true_when_mem0_installed(self) -> None:
        """When mem0 is importable, returns True."""
        with patch.dict("sys.modules", {"mem0": object()}):
            assert is_mem0_available() is True

    def test_returns_false_when_mem0_not_installed(self) -> None:
        """When mem0 raises ImportError, returns False.

        Uses a selective side_effect that only blocks ``mem0`` imports
        so coverage's own internal imports (``coverage.sysmon`` etc.)
        are not affected.
        """
        import builtins as _builtins

        real_import = _builtins.__import__

        def _block_mem0_import(name: str, *args: Any, **kwargs: Any) -> object:
            if name == "mem0":
                raise ImportError("no mem0")
            return real_import(name, *args, **kwargs)

        with patch.object(_builtins, "__import__", side_effect=_block_mem0_import):
            assert is_mem0_available() is False


# ---------------------------------------------------------------------------
# detect_provider_from_env
# ---------------------------------------------------------------------------


class TestDetectProviderFromEnv:
    """Tests for detect_provider_from_env environment detection."""

    def test_detects_openai_from_env(self) -> None:
        """OPENAI_API_KEY set → returns ProviderEnvConfig with openai."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-123"}, clear=True):
            result = detect_provider_from_env()

        assert isinstance(result, ProviderEnvConfig)
        assert result.provider == "openai"
        assert result.api_key == "sk-test-123"
        assert result.base_url is None

    def test_detects_openai_with_base_url(self) -> None:
        """OPENAI_API_KEY + OPENAI_BASE_URL → base_url is included."""
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test-123", "OPENAI_BASE_URL": "https://custom.api.com/v1"},
            clear=True,
        ):
            result = detect_provider_from_env()

        assert result is not None
        assert result.provider == "openai"
        assert result.base_url == "https://custom.api.com/v1"

    def test_detects_anthropic_from_env(self) -> None:
        """ANTHROPIC_API_KEY set (no OpenAI) → returns ProviderEnvConfig with anthropic."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-456"}, clear=True):
            result = detect_provider_from_env()

        assert isinstance(result, ProviderEnvConfig)
        assert result.provider == "anthropic"
        assert result.api_key == "sk-ant-456"

    def test_openai_takes_priority_over_anthropic(self) -> None:
        """Both keys set → openai wins (priority order)."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-oai-789",
                "ANTHROPIC_API_KEY": "sk-ant-000",
            },
            clear=True,
        ):
            result = detect_provider_from_env()

        assert result is not None
        assert result.provider == "openai"
        assert result.api_key == "sk-oai-789"

    def test_no_credentials_returns_none(self) -> None:
        """No API keys set → returns None."""
        with patch.dict(os.environ, {}, clear=True):
            result = detect_provider_from_env()

        assert result is None
