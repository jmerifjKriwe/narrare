"""
Text embedding generation — convenience re-exports from embedding_providers.

This module is maintained for backward compatibility.
All implementation lives in :mod:`narrare_core.llm.embedding_providers`.

``from narrare_core.llm.embeddings import embed_texts`` continues to work
with the same signature, plus an optional ``provider=`` keyword argument
for selecting a registered embedding provider by name.
"""

from narrare_core.llm.embedding_providers import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    available,
    embed_texts,
    get,
    register,
)

__all__ = [
    "EmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "available",
    "embed_texts",
    "get",
    "register",
]
