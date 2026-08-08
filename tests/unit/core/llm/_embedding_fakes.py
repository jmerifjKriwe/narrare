"""Shared MagicMock-spec fakes for embedding tests.

Extracted per RULE-04 (file size limits) so both ``test_embeddings.py`` and
``test_embedding_providers_leak.py`` can reuse the same spec classes without
duplication.  This module is prefixed with ``_`` so pytest does not collect
it as a test file.

See: docs/development/testing-standards.md — RULE-TEST-01
"""

from __future__ import annotations


class _FakeEmbeddingItem:
    """Fake for OpenAI embedding response item (has .index + .embedding)."""

    index = 0
    embedding = None


class _FakeEmbeddingResponse:
    """Fake for OpenAI create embeddings response (has .data)."""

    data = None


class _FakeEmbeddingsResource:
    """Fake for OpenAI embeddings resource (has .create method)."""

    def create(self, **kwargs) -> None: ...


class _FakeProvider:
    """Fake for an EmbeddingProvider protocol implementation."""

    default_model = ""
    default_dimension = 0

    async def embed_texts(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]]: ...
