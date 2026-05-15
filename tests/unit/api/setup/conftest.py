"""Shared fixtures for setup unit tests."""

from __future__ import annotations

import pytest

# Re-export fixtures from _complete_helpers so pytest discovers them.
# Underscore-prefixed modules are not scanned by pytest, so conftest
# must explicitly import the decorated fixtures.
from ._complete_helpers import (  # noqa: F401
    complete_service,  # pyright: ignore[reportUnusedImport]
    fake_demo_loader,  # pyright: ignore[reportUnusedImport]
    fake_provider_service,  # pyright: ignore[reportUnusedImport]
)


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Ensure NARRARE_ENCRYPTION_KEY is set for all setup unit tests."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("NARRARE_ENCRYPTION_KEY", Fernet.generate_key().decode())
