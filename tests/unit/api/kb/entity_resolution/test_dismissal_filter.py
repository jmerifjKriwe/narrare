"""Rejection-ledger filtering at the analysis read seam (ADR-085 P4, §7).

Split from ``test_analysis_service.py`` per RULE-04. Pins the read-time
dismissal semantics: a rejected suggestion never surfaces again (fresh
analyze OR cached read), the served band stats are recounted over the
kept suggestions, and the CACHE PAYLOAD STAYS UNFILTERED — the ledger
applies when results are served, so a rejection also covers results
cached before it (and remains auditable in the payload).
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare_core.kb.resolution.models import EntitySnapshot, EntryProvenance
from narrare_core.kb.resolution.scoring import ResolutionEngine

if TYPE_CHECKING:
    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
    from narrare.kb.entity_resolution.contracts import (
        DismissedSuggestionStoreProtocol,
        SnapshotBuilderProtocol,
    )
    from narrare_core.writing.session_manager import SessionCacheProtocol

# Identical embeddings -> cosine 1.0 >= EMBEDDING_COS -> S5 = +1.0.
SAME_EMBEDDING: tuple[float, ...] = (1.0, 0.0)

NOVEL = uuid4()
USER = uuid4()


# --- Fakes ----------------------------------------------------------------------


class _FakeBuilder:
    """Fake SnapshotBuilderProtocol returning a canned snapshot tuple."""

    def __init__(self, snapshots: tuple[EntitySnapshot, ...]) -> None:
        self.snapshots = snapshots

    async def build(self, novel_id: UUID) -> tuple[EntitySnapshot, ...]:
        return self.snapshots


class _FakeCache:
    """Dict-backed SessionCacheProtocol fake exposing the raw envelope store."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _FakeDismissed:
    """In-memory DismissedSuggestionStore fake (per-novel rejected ids)."""

    def __init__(self) -> None:
        self._rejected: dict[UUID, set[str]] = {}

    def reject(self, novel_id: UUID, suggestion_id: str) -> None:
        self._rejected.setdefault(novel_id, set()).add(suggestion_id)

    async def rejected_ids(self, novel_id: UUID) -> frozenset[str]:
        return frozenset(self._rejected.get(novel_id, set()))

    async def dismiss(self, novel_id: UUID, suggestion_id: str) -> None:
        self.reject(novel_id, suggestion_id)


# --- Helpers --------------------------------------------------------------------


def _provenance(first: int, last: int) -> EntryProvenance:
    return EntryProvenance(
        chapters=tuple(range(first, last + 1)),
        first_seen_chapter=first,
        last_seen_chapter=last,
        name_variants=(),
    )


def _snapshot(name: str, provenance: EntryProvenance) -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=uuid4(),
        name=name,
        entity_type="character",
        status="active",
        metadata={},
        provenance=provenance,
        neighbor_ids=frozenset(),
        embedding=SAME_EMBEDDING,
    )


def _duplicate_pair() -> tuple[EntitySnapshot, EntitySnapshot]:
    """§4 worked example: "Anna" (ch-01-03) vs "Anna Meyer" (ch-04+)."""
    anna = _snapshot("Anna", _provenance(1, 3))
    anna_meyer = _snapshot("Anna Meyer", _provenance(4, 6))
    return anna, anna_meyer


def _make_service(
    snapshots: tuple[EntitySnapshot, ...],
    dismissed: _FakeDismissed | None = None,
) -> tuple[ResolutionAnalysisService, _FakeCache]:
    from narrare.kb.entity_resolution.analysis_cache import ResolutionAnalysisCache
    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService

    fake_cache = _FakeCache()
    service = ResolutionAnalysisService(
        builder=cast("SnapshotBuilderProtocol", _FakeBuilder(snapshots)),
        engine=ResolutionEngine(),
        cache=ResolutionAnalysisCache(cast("SessionCacheProtocol", fake_cache)),
        dismissed=cast("DismissedSuggestionStoreProtocol | None", dismissed),
    )
    return service, fake_cache


def _expected_suggestion_id(a: UUID, b: UUID) -> str:
    lo, hi = sorted((str(a), str(b)))
    return hashlib.sha256(f"{lo}{hi}".encode()).hexdigest()[:16]


# --- Rejected suggestions filtered at the read seam (§7 reject) --------------------


class TestDismissalFilter:
    async def test_rejected_suggestion_filtered_from_analyze_response(self) -> None:
        """A rejected pair never surfaces again; band stats are recounted."""
        anna, anna_meyer = _duplicate_pair()
        store = _FakeDismissed()
        service, _ = _make_service((anna, anna_meyer), dismissed=store)
        first = await service.analyze(NOVEL, USER)
        pair_id = first.suggestions[0].suggestion_id
        store.reject(NOVEL, pair_id)

        after = await service.analyze(NOVEL, USER)

        assert [s.suggestion_id for s in after.suggestions] == []
        assert after.stats.auto_eligible == 0
        assert after.stats.review == 0
        assert after.stats.suppressed == 0

    async def test_rejected_suggestion_filtered_from_cached_read(self) -> None:
        """get_cached applies the ledger retroactively (cache_hit stays True)."""
        anna, anna_meyer = _duplicate_pair()
        store = _FakeDismissed()
        service, _ = _make_service((anna, anna_meyer), dismissed=store)
        first = await service.analyze(NOVEL, USER)
        pair_id = first.suggestions[0].suggestion_id
        store.reject(NOVEL, pair_id)

        after = await service.get_cached(NOVEL)

        assert after.cache_hit is True
        assert after.suggestions == []

    async def test_cache_payload_stays_unfiltered(self) -> None:
        """The ledger is applied at READ time — the payload keeps the pair.

        Filtering at write time would bake rejections into the cache and
        make them un-auditable; read-time filtering applies retroactively
        to results cached before the rejection.
        """
        anna, anna_meyer = _duplicate_pair()
        store = _FakeDismissed()
        service, cache = _make_service((anna, anna_meyer), dismissed=store)
        first = await service.analyze(NOVEL, USER)
        pair_id = first.suggestions[0].suggestion_id
        store.reject(NOVEL, pair_id)
        await service.get_cached(NOVEL)

        (raw,) = cache._store.values()
        payload = json.loads(json.loads(raw)["payload"])
        surfaced = [s["suggestion_id"] for s in payload["suggestions"]]
        assert pair_id in surfaced
        assert pair_id == _expected_suggestion_id(anna.entry_id, anna_meyer.entry_id)
