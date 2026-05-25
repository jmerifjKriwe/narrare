"""Shared fixtures for embedding service unit tests.

Provides ``FakeEmbeddingRepository`` (imported from tests.fakes) and
common fixtures used across generate, search, and lifecycle test files.
"""

from __future__ import annotations

import pytest

from narrare.embeddings.service import EmbeddingService
from tests.fakes import FakeEmbeddingRepository


@pytest.fixture
def fake_repo() -> FakeEmbeddingRepository:
    return FakeEmbeddingRepository()


@pytest.fixture
def service(fake_repo: FakeEmbeddingRepository) -> EmbeddingService:
    return EmbeddingService(fake_repo)
