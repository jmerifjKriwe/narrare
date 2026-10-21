"""Startup configuration is observable and fails fast on a schema mismatch."""

import logging

import pytest

from app.kernel.embeddings import SCHEMA_DIMENSIONS, validate_configuration


def test_the_active_providers_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="narrare"):
        validate_configuration()
    assert "llm=fake" in caplog.text
    assert "embedding=fake" in caplog.text
    assert f"dimensions={SCHEMA_DIMENSIONS}" in caplog.text


def test_a_dimension_change_without_a_migration_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NARRE_EMBEDDING_DIMENSIONS", str(SCHEMA_DIMENSIONS * 2))
    with pytest.raises(RuntimeError, match="migration"):
        validate_configuration()
