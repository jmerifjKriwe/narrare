"""Startup configuration is observable and fails fast on a mismatch."""

import logging

import pytest

from app.kernel.configuration import validate_configuration
from app.kernel.embeddings import SCHEMA_DIMENSIONS


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


def test_a_half_configured_real_provider_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("NARRE_LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("NARRE_LLM_MODEL", raising=False)
    monkeypatch.delenv("NARRE_LLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="NARRE_LLM_MODEL"):
        validate_configuration()


def test_an_unknown_provider_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "nonsense")
    with pytest.raises(RuntimeError, match="unknown LLM provider"):
        validate_configuration()


def test_the_catalog_builds_every_entry_it_advertises() -> None:
    from app.kernel.llm import PROVIDERS

    for name, build in PROVIDERS.items():
        provider = build()
        assert isinstance(provider.describe(), str), name
        assert isinstance(provider.configuration_problems(), list), name
