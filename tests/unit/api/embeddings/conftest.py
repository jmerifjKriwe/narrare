"""Shared fixtures for embedding service unit tests.

Provides ``FakeEmbeddingRepository`` (imported from tests.fakes) and
common fixtures used across generate, search, and lifecycle test files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare.embeddings.service import EmbeddingService
from narrare_core.settings import get_core_settings
from tests.fakes import FakeEmbeddingRepository

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest import MonkeyPatch


@pytest.fixture
def fake_repo() -> FakeEmbeddingRepository:
    return FakeEmbeddingRepository()


@pytest.fixture
def service(fake_repo: FakeEmbeddingRepository) -> EmbeddingService:
    return EmbeddingService(fake_repo)


# ---------------------------------------------------------------------------
# ADR-090 rerank flag control (ADR-071 §8 env + cache-clear pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def rerank_on(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Enable the ADR-090 rerank pilot flag."""
    monkeypatch.setenv("NARRARE_EMBEDDING_RERANK", "true")
    get_core_settings.cache_clear()
    yield
    get_core_settings.cache_clear()


@pytest.fixture
def rerank_off(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Pin the ADR-090 flag OFF (the shipped default) regardless of env."""
    monkeypatch.delenv("NARRARE_EMBEDDING_RERANK", raising=False)
    get_core_settings.cache_clear()
    yield
    get_core_settings.cache_clear()
