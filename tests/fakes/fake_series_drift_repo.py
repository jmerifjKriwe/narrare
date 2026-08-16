"""Fake SeriesDrift repository for unit tests (ADR-030 — Fake-based).

Implements ``SeriesDriftRepositoryProtocol`` with in-memory storage keyed by
``novel_id``. ``store_section`` mirrors the real repository's semantics:
per-section document merge (shallow dict merge under ``result[section]``),
fingerprint overwrite, ``generated_at`` refresh. Records every call.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from narrare.series.series_drift_models import SeriesDriftResult
from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    import uuid

    from narrare.series.series_drift_contracts import DriftSection


class FakeSeriesDriftRepository:
    """In-memory fake for ``SeriesDriftRepositoryProtocol``."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, SeriesDriftResult] = {}
        self.calls: list[CallRecord] = []
        # Test hook: when set, store_section raises this instead of storing.
        self.raise_on_store: Exception | None = None

    def seed(self, *rows: SeriesDriftResult) -> None:
        """Pre-populate the store with drift-result rows."""
        for row in rows:
            self._store[row.novel_id] = row

    async def get(self, novel_id: uuid.UUID) -> SeriesDriftResult | None:
        self.calls.append(CallRecord("get", kwargs={"novel_id": novel_id}))
        return self._store.get(novel_id)

    async def store_section(
        self,
        novel_id: uuid.UUID,
        *,
        section: DriftSection,
        document: dict,
        fingerprint: str,
    ) -> None:
        self.calls.append(
            CallRecord(
                "store_section",
                kwargs={
                    "novel_id": novel_id,
                    "section": section,
                    "document": document,
                    "fingerprint": fingerprint,
                },
            )
        )
        if self.raise_on_store is not None:
            raise self.raise_on_store
        row = self._store.get(novel_id)
        if row is None:
            row = SeriesDriftResult(novel_id=novel_id, result={})
            self._store[novel_id] = row
        merged = dict(row.result or {})
        merged[section] = document
        row.result = merged
        row.input_fingerprint = fingerprint
        # Stamp generated_at so callers reading it don't hit server defaults.
        row.generated_at = datetime.now(UTC)

    # -- assertion helpers (mirrors fake_band_summary_repo) ----------------

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called(self, method: str, **kwargs: Any) -> None:
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")

    def assert_not_called(self, method: str) -> None:
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")
