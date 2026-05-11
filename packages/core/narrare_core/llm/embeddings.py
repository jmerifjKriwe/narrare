"""
Text embedding generation.

This module is an approved RULE-01 exception: it imports the OpenAI client
directly because the batch embedding API requires direct client access for
performance (the pydantic-ai agent abstraction does not expose batch embedding).

See: pyproject.toml [tool.narrare.architecture.exceptions]
See: ADR-003 (approved exceptions register)

# narrare: allow-direct-llm  reason="Batch embedding API needs direct client for performance"
"""

from __future__ import annotations

import os
import time

import openai
import structlog

from narrare_core.shared.errors import EmbeddingError

logger = structlog.get_logger(__name__)

_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 100  # OpenAI recommended batch size


async def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed. Empty strings are skipped.
        model: Embedding model to use. Defaults to text-embedding-3-small.

    Returns:
        List of embedding vectors, one per input text.
        Empty strings return zero vectors of the correct dimension.

    Raises:
        EmbeddingError: If the embedding API call fails.
    """
    if not texts:
        return []

    model_name = model or os.environ.get("DEFAULT_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)

    # Separate empty strings (return zero vectors) from real texts
    indices_to_embed: list[int] = []
    texts_to_embed: list[str] = []
    for i, text in enumerate(texts):
        if text.strip():
            indices_to_embed.append(i)
            texts_to_embed.append(text)

    if not texts_to_embed:
        # All empty — return zero vectors
        # We don't know dimension without an API call; use 1536 (text-embedding-3-small)
        dim = 1536
        return [[0.0] * dim for _ in texts]

    client = openai.AsyncOpenAI()

    all_embeddings: list[list[float]] = []
    start = time.monotonic()

    try:
        # Process in batches
        for batch_start in range(0, len(texts_to_embed), _BATCH_SIZE):
            batch = texts_to_embed[batch_start : batch_start + _BATCH_SIZE]
            response = await client.embeddings.create(
                input=batch,
                model=model_name,
            )
            for item in sorted(response.data, key=lambda x: x.index):
                all_embeddings.append(item.embedding)

        elapsed = time.monotonic() - start
        _ = sum(len(t.split()) for t in texts_to_embed)  # approximate, unused

        logger.info(
            "embeddings_generated",
            count=len(texts_to_embed),
            model=model_name,
            duration_ms=round(elapsed * 1000),
        )

    except openai.OpenAIError as e:
        raise EmbeddingError(f"Embedding generation failed: {e}") from e

    # Re-assemble: place real embeddings at their original indices,
    # fill missing (empty text) positions with zero vectors
    dim = len(all_embeddings[0]) if all_embeddings else 1536
    result: list[list[float]] = [[0.0] * dim for _ in texts]
    for result_idx, orig_idx in enumerate(indices_to_embed):
        result[orig_idx] = all_embeddings[result_idx]

    return result
