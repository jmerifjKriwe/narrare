"""Startup configuration is observable and fails fast on a mismatch."""

import logging

import pytest

from app.kernel.configuration import validate_configuration


def test_the_active_providers_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="narrare"):
        validate_configuration()
    assert "llm=fake" in caplog.text
    assert "embedding=fake" in caplog.text


def test_a_half_configured_real_provider_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("NARRE_LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("NARRE_LLM_MODEL", raising=False)
    monkeypatch.delenv("NARRE_LLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="NARRE_LLM_MODEL"):
        validate_configuration()


def test_a_half_configured_real_embedding_provider_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NARRE_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("NARRE_EMBEDDING_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("NARRE_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("NARRE_EMBEDDING_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="NARRE_EMBEDDING_MODEL"):
        validate_configuration()


def test_an_unknown_provider_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "nonsense")
    with pytest.raises(RuntimeError, match="unknown LLM provider"):
        validate_configuration()


def test_the_catalog_builds_every_entry_it_advertises() -> None:
    from app.kernel.embeddings import EMBEDDING_PROVIDERS
    from app.kernel.llm import PROVIDERS

    for name, build in PROVIDERS.items():
        provider = build()
        assert isinstance(provider.describe(), str), name
        assert isinstance(provider.configuration_problems(), list), name

    for name, build in EMBEDDING_PROVIDERS.items():
        embeddings = build()
        assert isinstance(embeddings.describe(), str), name
        assert isinstance(embeddings.configuration_problems(), list), name
