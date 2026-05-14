"""Shared fixtures for setup unit tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Ensure NARRARE_ENCRYPTION_KEY is set for all setup unit tests."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("NARRARE_ENCRYPTION_KEY", Fernet.generate_key().decode())
