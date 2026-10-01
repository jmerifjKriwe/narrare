"""Optional local multi-vector rerank tier (ADR-090).

Post-retrieval stage over the existing dense first stage: pgvector top-K
with hybrid scoring (unchanged) -> MaxSim rerank -> top-N. No pgvector
schema or index change, no persistence — ``MultiVectorEncoder`` only
scores query x document at rerank time (ADR-090 Decision 1).

``sentence_transformers`` is imported lazily and ONLY in this module
(RULE-08); importing this module never imports torch. Callers degrade to
``NullReranker`` when the ``embeddings`` extra is absent (RULE-11). The
default checkpoint is pinned (ADR-090 Decision 5) — never the ST library
default, which drifts between releases and breaks eval comparability.

Candidate texts are caller-supplied (ADR-090 Decision 4): search rows
carry no text, so the Backend layer fetches texts via its own
repositories, builds fully materialized ``RerankCandidate`` objects, and
Core stays free of I/O.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import structlog

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

logger = structlog.get_logger(__name__)

DEFAULT_RERANK_MODEL = "lightonai/LateOn"
"""Pinned rerank checkpoint (ADR-090 Decision 5) — never the ST library default."""

__all__ = [
    "DEFAULT_RERANK_MODEL",
    "MultiVectorReranker",
    "NullReranker",
    "RerankCandidate",
    "Reranker",
    "is_rerank_available",
    "rerank_candidates",
]


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    """A fully materialized retrieval candidate (ADR-090 Decision 3).

    Attributes:
        source_id: UUID of the source entity.
        source_type: Content type label (e.g. "kb_entry").
        text: Candidate text to rerank, supplied by the caller.
        base_score: Pre-rerank hybrid score — kept for observability and
            tie-breaking; the rerank score is the new sort key.
    """

    source_id: UUID
    source_type: str
    text: str
    base_score: float


@runtime_checkable
class Reranker(Protocol):
    """Contract for the rerank tier (RULE-03, ADR-090 Decision 3).

    Implementations return candidates stable-sorted by rerank score
    descending, truncated to ``top_n``.
    """

    async def rerank(
        self, query: str, candidates: Sequence[RerankCandidate], *, top_n: int
    ) -> list[RerankCandidate]: ...


class NullReranker:
    """Degraded passthrough — input order (the first-stage ranking), truncated.

    Wired when the ``embeddings`` extra is absent or the rerank flag is
    off (ADR-090 Decision 6): the pre-rerank order survives unchanged.
    """

    async def rerank(
        self, query: str, candidates: Sequence[RerankCandidate], *, top_n: int
    ) -> list[RerankCandidate]:
        if top_n < 0:
            msg = f"top_n must be >= 0, got {top_n}"
            raise ValueError(msg)
        return list(candidates)[:top_n]


def is_rerank_available() -> bool:
    """Return True when the ``embeddings`` extra (sentence-transformers>=6.1,<7) is installed.

    Mirrors ``narrare_core.memory.availability.is_mem0_available``.
    """
    try:
        import sentence_transformers as _sentence_transformers
    except ImportError:
        return False
    del _sentence_transformers
    return True


class _EncoderSurface(Protocol):
    """Typed seam over the exact ``MultiVectorEncoder`` surface this module uses.

    The upstream public overloads are partially unknown to pyright (their
    ``SingleInput`` alias spans multimodal input types). This private
    Protocol narrows to the call shapes bound by ADR-090 — encode one query
    / K documents, MaxSim-similarity them — so the hot path stays fully
    typed without any suppression (RULE-23: ``cast`` over ignore).
    """

    def encode_query(self, inputs: Sequence[str]) -> Sequence[object]: ...

    def encode_document(self, inputs: Sequence[str]) -> Sequence[object]: ...

    def similarity(
        self, embeddings1: Sequence[object], embeddings2: Sequence[object]
    ) -> Sequence[Sequence[float]]: ...


# Process-wide encoder cache keyed by model name (ADR-090 Decision 6): the
# first rerank call pays the checkpoint download/load; later calls reuse it.
_encoder_cache: dict[str, _EncoderSurface] = {}
_encoder_cache_lock = threading.Lock()


class MultiVectorReranker:
    """Local late-interaction reranker on ST v6 ``MultiVectorEncoder``.

    ``sentence_transformers`` is imported lazily inside this class only
    (RULE-08). Construction probes availability but never loads a
    checkpoint — the encoder loads on the first ``rerank`` call, inside
    the degradation boundary (ADR-090 Decision 6): load or scoring
    failures propagate to the caller, which degrades to the pre-rerank
    top-N. Encoding and scoring are blocking (CPU-bound) and therefore
    run in a worker thread via ``asyncio.to_thread``.
    """

    def __init__(self, model_name: str = DEFAULT_RERANK_MODEL) -> None:
        try:
            from sentence_transformers import MultiVectorEncoder
        except ImportError as exc:
            raise ImportError(
                "MultiVectorReranker requires the 'embeddings' extra "
                "(sentence-transformers>=6.1,<7); install it with "
                "`uv sync --all-packages --extra embeddings` or wire NullReranker instead."
            ) from exc
        del MultiVectorEncoder  # availability probe only — the encoder loads on first use
        self._model_name = model_name

    async def rerank(
        self, query: str, candidates: Sequence[RerankCandidate], *, top_n: int
    ) -> list[RerankCandidate]:
        if top_n < 0:
            msg = f"top_n must be >= 0, got {top_n}"
            raise ValueError(msg)
        if not candidates:
            return []
        texts = [candidate.text for candidate in candidates]
        scores = await asyncio.to_thread(self._score_sync, query, texts)
        return await rerank_candidates(candidates, scores, keep=top_n)

    def _score_sync(self, query: str, texts: list[str]) -> list[float]:
        """MaxSim scores of one query against all candidate texts (blocking).

        Exact call sequence per ADR-090 "Binding call sequence for Task 14";
        ``similarity`` (not ``similarity_pairwise``) — one query against
        K documents.
        """
        encoder = _load_encoder(self._model_name)
        query_embeddings = encoder.encode_query([query])
        document_embeddings = encoder.encode_document(texts)
        similarity = encoder.similarity(query_embeddings, document_embeddings)
        return [float(score) for score in similarity[0]]


def _load_encoder(model_name: str) -> _EncoderSurface:
    """Load (or reuse) the process-wide encoder for ``model_name``.

    The single ``cast`` narrows the constructed encoder to the typed seam
    (see ``_EncoderSurface``) — checked narrowing is unavailable because
    the upstream overloads are partially unknown.
    """
    from sentence_transformers import MultiVectorEncoder

    with _encoder_cache_lock:
        encoder = _encoder_cache.get(model_name)
        if encoder is None:
            encoder = cast("_EncoderSurface", MultiVectorEncoder(model_name))
            _encoder_cache[model_name] = encoder
            logger.info("embedding_rerank_encoder_loaded", model=model_name)
        return encoder


async def rerank_candidates(
    candidates: Sequence[RerankCandidate],
    scores: Sequence[float],
    *,
    keep: int | None = None,
) -> list[RerankCandidate]:
    """Pure reorder: stable sort by score descending, optionally keep top ``keep``.

    Args:
        candidates: Candidates to reorder; must match ``scores`` one-to-one.
        scores: One rerank score per candidate (the new sort key).
        keep: Truncate the result to the top ``keep`` candidates; ``None``
            keeps all.

    Returns:
        New list of candidates sorted by score descending; candidates with
        identical scores keep their original relative order (stable sort).

    Raises:
        ValueError: If ``scores`` does not match ``candidates`` one-to-one,
            or ``keep`` is negative.
    """
    if len(candidates) != len(scores):
        msg = (
            f"one score per candidate required: got {len(candidates)} "
            f"candidates and {len(scores)} scores"
        )
        raise ValueError(msg)
    if keep is not None and keep < 0:
        msg = f"keep must be >= 0, got {keep}"
        raise ValueError(msg)

    # Length equality is validated above, so zip can never truncate here.
    scored: list[tuple[float, RerankCandidate]] = [
        (score, candidate) for score, candidate in zip(scores, candidates, strict=False)
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    ranked = [candidate for _, candidate in scored]
    if keep is not None:
        return ranked[:keep]
    return ranked
