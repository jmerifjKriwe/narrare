"""Tests for narrare_core.memory.availability — is_mem0_available."""

from __future__ import annotations

from unittest.mock import patch

from narrare_core.memory.availability import is_mem0_available


class TestIsMem0Available:
    """Tests for is_mem0_available package detection."""

    def test_returns_true_when_mem0_installed(self) -> None:
        """When mem0 is importable, returns True."""
        with patch.dict("sys.modules", {"mem0": object()}):
            assert is_mem0_available() is True

    def test_returns_false_when_mem0_not_installed(self) -> None:
        """When mem0 raises ImportError, returns False."""
        with patch("builtins.__import__", side_effect=ImportError("no mem0")):
            assert is_mem0_available() is False
