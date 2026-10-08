"""Fake writing-stats recorder for unit tests (STATS-001)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid


class FakeWritingStatsRecorder:
    """Recording fake for the ``WritingStatsRecorder`` Protocol (ADR-030).

    Records every ``record_delta`` call so tests can pin exactly-once
    delivery and the signed delta at the call site. Mirrors the real
    contract shape: returns normally on every call — zero-delta skipping
    and never-raises failure absorption live inside the real recorder, so
    this fake deliberately does NOT skip zero deltas (call sites must be
    pinned on always calling, per the STATS-001 contract).
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def deltas(self) -> list[int]:
        """Just the recorded deltas, in call order."""
        return [int(call["delta_words"]) for call in self.calls]

    async def record_delta(
        self,
        *,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        delta_words: int,
    ) -> None:
        self.calls.append(
            {
                "user_id": user_id,
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "delta_words": delta_words,
            }
        )
