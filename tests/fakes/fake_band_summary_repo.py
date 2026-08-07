"""Fake BandSummary repository for unit tests (ADR-030 — Fake-based, not MagicMock).

Implements ``BandSummaryRepositoryProtocol`` with in-memory storage keyed by
``novel_id`` (mirroring the 1:1 PK invariant of the real model). Records every
call so service tests can assert interaction (mirrors ``fake_chapter_repo.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from narrare.series.band_summary_models import BandSummary
from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    import uuid


class FakeBandSummaryRepository:
    """In-memory fake for ``BandSummaryRepositoryProtocol``.

    Keyed by ``novel_id`` (1:1 invariant). All mutating methods upsert like the
    real repository: a missing row is created on demand.
    """

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, BandSummary] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *summaries: BandSummary) -> None:
        """Pre-populate the store with band summaries."""
        for s in summaries:
            self._store[s.novel_id] = s

    def _get_or_create(self, novel_id: uuid.UUID) -> BandSummary:
        summary = self._store.get(novel_id)
        if summary is None:
            summary = BandSummary(novel_id=novel_id)
            # Stamp generated_at so callers reading it don't hit server defaults.
            summary.generated_at = datetime.now(UTC)
            self._store[novel_id] = summary
        return summary

    async def get(self, novel_id: uuid.UUID) -> BandSummary | None:
        self.calls.append(CallRecord("get", kwargs={"novel_id": novel_id}))
        return self._store.get(novel_id)

    async def upsert(
        self,
        novel_id: uuid.UUID,
        full_summary: str,
        short_summary: str,
    ) -> BandSummary:
        self.calls.append(
            CallRecord(
                "upsert",
                kwargs={
                    "novel_id": novel_id,
                    "full_summary": full_summary,
                    "short_summary": short_summary,
                },
            )
        )
        summary = self._get_or_create(novel_id)
        summary.full_summary = full_summary
        summary.short_summary = short_summary
        summary.generated_at = datetime.now(UTC)
        return summary

    async def set_override(self, novel_id: uuid.UUID, override: str) -> BandSummary:
        self.calls.append(
            CallRecord("set_override", kwargs={"novel_id": novel_id, "override": override})
        )
        summary = self._get_or_create(novel_id)
        summary.override = override
        return summary

    async def clear_override(self, novel_id: uuid.UUID) -> BandSummary:
        self.calls.append(CallRecord("clear_override", kwargs={"novel_id": novel_id}))
        summary = self._get_or_create(novel_id)
        summary.override = None
        return summary

    # -- assertion helpers ------------------------------------------------

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called(self, method: str, **kwargs: Any) -> None:
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")

    def assert_called_once(self, method: str) -> None:
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_not_called(self, method: str) -> None:
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")
