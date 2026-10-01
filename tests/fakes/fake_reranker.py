"""Fakes for the ADR-090 rerank tier seams — no checkpoint download.

``FakeReranker`` implements the Core ``Reranker`` Protocol (recording
calls, ordering by configured scores); ``FakeTextFetcher`` matches the
Backend ``TextFetcher`` alias (recording requests, returning configured
texts). Unit tests fake at the Protocol boundary — real-checkpoint runs
are pilot (Task 16) territory, not CI (ADR-090 test contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare_core.embeddings.rerank import RerankCandidate


class FakeReranker:
    """Fake ``Reranker`` — records calls, orders by configured scores.

    Candidates without an entry in ``scores`` rank at 0.0; ties keep
    input order (stable sort), mirroring the Core contract.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[RerankCandidate], int]] = []
        self.scores: dict[UUID, float] = {}
        self.error: Exception | None = None

    async def rerank(
        self, query: str, candidates: Sequence[RerankCandidate], *, top_n: int
    ) -> list[RerankCandidate]:
        self.calls.append((query, list(candidates), top_n))
        if self.error is not None:
            raise self.error
        ordered = sorted(candidates, key=lambda c: self.scores.get(c.source_id, 0.0), reverse=True)
        return ordered[:top_n]


class FakeTextFetcher:
    """Fake ``TextFetcher`` — records requests, returns the configured texts.

    Ids absent from ``texts`` are absent from the returned mapping — the
    rerank stage treats them as textless (first-stage position kept).
    """

    def __init__(self, texts: dict[UUID, str] | None = None) -> None:
        self.texts: dict[UUID, str] = dict(texts or {})
        self.requests: list[list[UUID]] = []
        self.error: Exception | None = None

    async def __call__(self, source_ids: Sequence[UUID]) -> dict[UUID, str]:
        self.requests.append(list(source_ids))
        if self.error is not None:
            raise self.error
        return {
            source_id: self.texts[source_id] for source_id in source_ids if source_id in self.texts
        }
