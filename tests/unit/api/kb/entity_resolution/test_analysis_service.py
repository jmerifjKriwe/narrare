"""Unit tests for the KB resolution analysis service (ADR-085 P3, spec §7).

The service turns snapshots into scored, banded suggestions with caching.
Pins taken from spec §4 worked examples and §7 semantics: the duplicate
"Anna"/"Anna Meyer" pair surfaces AUTO_ELIGIBLE at confidence 0.895, the
distractor "Anna Meyer"/"Anna Meier" pair is structurally SUPPRESSED
(counted + logged per RULE-11, never surfaced), suggestion identity is a
stateless sha256 hash of the sorted entry-id strings, and the analysis
cache mirrors the consistency-cache pattern (novel-scoped, validated
against the entries hash, explicit invalidation, ``refresh`` recompute).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from structlog.testing import capture_logs

from narrare_core.kb.resolution.models import EntitySnapshot, EntryProvenance
from narrare_core.kb.resolution.scoring import ResolutionEngine

if TYPE_CHECKING:
    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
    from narrare.kb.entity_resolution.contracts import (
        DismissedSuggestionStoreProtocol,
        SnapshotBuilderProtocol,
    )
    from narrare.kb.entity_resolution.schemas_resolution import ResolutionAnalysisResponse
    from narrare_core.writing.session_manager import SessionCacheProtocol

# Identical embeddings -> cosine 1.0 >= EMBEDDING_COS -> S5 = +1.0.
SAME_EMBEDDING: tuple[float, ...] = (1.0, 0.0)

NOVEL = uuid4()
USER = uuid4()


# --- Fakes ----------------------------------------------------------------------


class _FakeBuilder:
    """Fake SnapshotBuilderProtocol returning a canned snapshot tuple."""

    def __init__(self, snapshots: tuple[EntitySnapshot, ...] = ()) -> None:
        self.snapshots = snapshots
        self.build_calls = 0

    async def build(self, novel_id: UUID) -> tuple[EntitySnapshot, ...]:
        self.build_calls += 1
        return self.snapshots


class _FakeCache:
    """Dict-backed SessionCacheProtocol fake counting writes."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.set_calls = 0

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._store[key] = value
        self.set_calls += 1

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


# --- Helpers --------------------------------------------------------------------


def _provenance(first: int, last: int) -> EntryProvenance:
    return EntryProvenance(
        chapters=tuple(range(first, last + 1)),
        first_seen_chapter=first,
        last_seen_chapter=last,
        name_variants=(),
    )


def _snapshot(
    *,
    entry_id: UUID | None = None,
    name: str = "Anna Meyer",
    metadata: dict[str, object] | None = None,
    provenance: EntryProvenance | None = None,
    neighbor_ids: frozenset[UUID] | None = None,
    embedding: tuple[float, ...] | None = None,
) -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=entry_id if entry_id is not None else uuid4(),
        name=name,
        entity_type="character",
        status="active",
        metadata=dict(metadata or {}),
        provenance=provenance,
        neighbor_ids=neighbor_ids if neighbor_ids is not None else frozenset(),
        embedding=embedding,
    )


def _duplicate_pair() -> tuple[EntitySnapshot, EntitySnapshot]:
    """§4 worked example: "Anna" (ch-01-03) vs "Anna Meyer" (ch-04+) → 0.895."""
    shared = frozenset({uuid4(), uuid4()})
    anna = _snapshot(
        name="Anna",
        metadata={"age (2017)": 24},
        provenance=_provenance(1, 3),
        neighbor_ids=shared | {uuid4()},
        embedding=SAME_EMBEDDING,
    )
    anna_meyer = _snapshot(
        name="Anna Meyer",
        metadata={"age (2018)": 25},
        provenance=_provenance(4, 6),
        neighbor_ids=shared | {uuid4()},
        embedding=SAME_EMBEDDING,
    )
    return anna, anna_meyer


def _distractor_pair() -> tuple[EntitySnapshot, EntitySnapshot]:
    """§4 worked example: "Anna Meyer" (ch-08-10) vs "Anna Meier" (ch-09-12),
    co-active → co-existence veto → SUPPRESSED."""
    anna_meyer = _snapshot(
        name="Anna Meyer",
        provenance=_provenance(8, 10),
        neighbor_ids=frozenset({uuid4(), uuid4()}),
        embedding=SAME_EMBEDDING,
    )
    anna_meier = _snapshot(
        name="Anna Meier",
        provenance=_provenance(9, 12),
        neighbor_ids=frozenset({uuid4(), uuid4()}),
        embedding=SAME_EMBEDDING,
    )
    return anna_meyer, anna_meier


def _make_service(
    snapshots: tuple[EntitySnapshot, ...],
    cache: _FakeCache | None = None,
    dismissed: object = None,
) -> tuple[ResolutionAnalysisService, _FakeBuilder, _FakeCache]:
    from narrare.kb.entity_resolution.analysis_cache import ResolutionAnalysisCache
    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService

    builder = _FakeBuilder(snapshots)
    fake_cache = cache if cache is not None else _FakeCache()
    service = ResolutionAnalysisService(
        builder=cast("SnapshotBuilderProtocol", builder),
        engine=ResolutionEngine(),
        cache=ResolutionAnalysisCache(cast("SessionCacheProtocol", fake_cache)),
        dismissed=cast("DismissedSuggestionStoreProtocol", dismissed),
    )
    return service, builder, fake_cache


async def _analyze(
    snapshots: tuple[EntitySnapshot, ...],
    **kwargs: bool,
) -> ResolutionAnalysisResponse:
    service, _, _ = _make_service(snapshots)
    return await service.analyze(NOVEL, USER, **kwargs)


def _expected_suggestion_id(a: UUID, b: UUID) -> str:
    lo, hi = sorted((str(a), str(b)))
    return hashlib.sha256(f"{lo}{hi}".encode()).hexdigest()[:16]


# --- Duplicate pair surfaced (§4 worked example) ---------------------------------


class TestDuplicatePairSurfaced:
    async def test_worked_example_surfaced_auto_eligible_0895(self) -> None:
        anna, anna_meyer = _duplicate_pair()
        response = await _analyze((anna, anna_meyer))

        assert response.cache_hit is False
        assert len(response.suggestions) == 1
        suggestion = response.suggestions[0]
        assert suggestion.confidence == pytest.approx(0.895)
        assert suggestion.band == "AUTO_ELIGIBLE"
        assert suggestion.auto_merge_eligible is True
        lo, hi = sorted((anna.entry_id, anna_meyer.entry_id))
        assert suggestion.entry_a_id == lo
        assert suggestion.entry_b_id == hi
        names = {anna.entry_id: "Anna", anna_meyer.entry_id: "Anna Meyer"}
        assert suggestion.name_a == names[lo]
        assert suggestion.name_b == names[hi]
        assert response.stats.review == 0
        assert response.stats.auto_eligible == 1
        assert response.stats.suppressed == 0

    async def test_suggestion_evidence_carries_five_signals(self) -> None:
        anna, anna_meyer = _duplicate_pair()
        response = await _analyze((anna, anna_meyer))

        evidence = response.suggestions[0].signals
        assert tuple(e.signal for e in evidence) == (
            "name_tier",
            "temporal",
            "attributes",
            "neighborhood",
            "embedding",
        )
        assert evidence[0].value == pytest.approx(0.7)  # SUBSET tier
        assert evidence[1].value == pytest.approx(1.0)  # handoff
        assert all(e.veto is False for e in evidence)
        assert all(e.detail != "" for e in evidence)

    async def test_suggestion_id_matches_stateless_spec_hash(self) -> None:
        anna, anna_meyer = _duplicate_pair()
        response = await _analyze((anna, anna_meyer))

        expected = _expected_suggestion_id(anna.entry_id, anna_meyer.entry_id)
        assert response.suggestions[0].suggestion_id == expected


# --- Distractor suppressed (RULE-11: counted + logged, never surfaced) -----------


class TestDistractorSuppressed:
    async def test_distractor_not_surfaced_but_counted_suppressed(self) -> None:
        anna_meyer, anna_meier = _distractor_pair()
        response = await _analyze((anna_meyer, anna_meier))

        assert response.suggestions == []
        assert response.stats.review == 0
        assert response.stats.auto_eligible == 0
        assert response.stats.suppressed == 1

    async def test_suppressed_pair_is_logged_not_silently_dropped(self) -> None:
        anna_meyer, anna_meier = _distractor_pair()
        service, _, _ = _make_service((anna_meyer, anna_meier))

        with capture_logs() as logs:
            await service.analyze(NOVEL, USER)

        suppressed = [e for e in logs if e["event"] == "resolution_pair_suppressed"]
        assert len(suppressed) == 1
        assert suppressed[0]["novel_id"] == str(NOVEL)
        assert suppressed[0]["vetoes"] == ["temporal"]
        lo, hi = sorted((str(anna_meyer.entry_id), str(anna_meier.entry_id)))
        assert suppressed[0]["entry_a_id"] == lo
        assert suppressed[0]["entry_b_id"] == hi


# --- Stateless suggestion identity ----------------------------------------------


class TestSuggestionIdStability:
    async def test_suggestion_id_stable_across_independent_services(self) -> None:
        anna, anna_meyer = _duplicate_pair()
        first = await _analyze((anna, anna_meyer))
        second = await _analyze((anna, anna_meyer))

        expected = _expected_suggestion_id(anna.entry_id, anna_meyer.entry_id)
        assert first.suggestions[0].suggestion_id == expected
        assert second.suggestions[0].suggestion_id == expected


# --- Caching (novel scope + entries hash; refresh; invalidate) -------------------


class TestCaching:
    async def test_second_analyze_hits_cache_with_identical_payload(self) -> None:
        service, builder, fake_cache = _make_service(_duplicate_pair())

        first = await service.analyze(NOVEL, USER)
        second = await service.analyze(NOVEL, USER)

        assert first.cache_hit is False
        assert second.cache_hit is True
        assert second.suggestions == first.suggestions
        assert second.stats == first.stats
        # Snapshots are rebuilt for the entries hash; the engine ran once only.
        assert builder.build_calls == 2
        assert fake_cache.set_calls == 1

    async def test_refresh_forces_recompute(self) -> None:
        service, _, fake_cache = _make_service(_duplicate_pair())

        first = await service.analyze(NOVEL, USER)
        refreshed = await service.analyze(NOVEL, USER, refresh=True)

        assert first.cache_hit is False
        assert refreshed.cache_hit is False
        assert refreshed.suggestions == first.suggestions
        assert fake_cache.set_calls == 2

    async def test_invalidate_forces_recompute_on_next_analyze(self) -> None:
        service, _, fake_cache = _make_service(_duplicate_pair())

        await service.analyze(NOVEL, USER)
        await service.invalidate(NOVEL)
        after = await service.analyze(NOVEL, USER)

        assert after.cache_hit is False
        assert fake_cache.set_calls == 2

    async def test_changed_entries_miss_cache_even_without_refresh(self) -> None:
        service, builder, fake_cache = _make_service(_duplicate_pair())
        await service.analyze(NOVEL, USER)

        # Same novel scope, different entry set → different entries hash.
        builder.snapshots = _distractor_pair()
        after = await service.analyze(NOVEL, USER)

        assert after.cache_hit is False
        assert fake_cache.set_calls == 2


# --- Band stats across multiple pairs --------------------------------------------


class TestBandStats:
    async def test_review_band_surfaced_with_auto_merge_eligible_false(self) -> None:
        # S1=0.7 + S2=+1 (handoff), everything else unknown → 0.545 REVIEW.
        anna = _snapshot(name="Anna", provenance=_provenance(1, 3))
        anna_meyer = _snapshot(name="Anna Meyer", provenance=_provenance(4, 6))

        response = await _analyze((anna, anna_meyer))

        assert len(response.suggestions) == 1
        suggestion = response.suggestions[0]
        assert suggestion.confidence == pytest.approx(0.545)
        assert suggestion.band == "REVIEW"
        assert suggestion.auto_merge_eligible is False
        assert response.stats.review == 1
        assert response.stats.auto_eligible == 0
        assert response.stats.suppressed == 0

    async def test_full_worked_example_scene_counts_all_bands(self) -> None:
        # All three §4 worked examples in one novel: Anna (ch-01-03) hands
        # off to Anna Meyer (ch-04+); distractor Anna Meier (ch-06+) overlaps
        # Anna Meyer's range (co-existence veto) and gaps out from Anna.
        shared = frozenset({uuid4(), uuid4()})
        anna = _snapshot(
            name="Anna",
            metadata={"age (2017)": 24},
            provenance=_provenance(1, 3),
            neighbor_ids=shared | {uuid4()},
            embedding=SAME_EMBEDDING,
        )
        anna_meyer = _snapshot(
            name="Anna Meyer",
            metadata={"age (2018)": 25},
            provenance=_provenance(4, 6),
            neighbor_ids=shared | {uuid4()},
            embedding=SAME_EMBEDDING,
        )
        anna_meier = _snapshot(
            name="Anna Meier",
            provenance=_provenance(6, 8),
            neighbor_ids=frozenset({uuid4(), uuid4()}),
            embedding=SAME_EMBEDDING,
        )
        service, _, _ = _make_service((anna_meier, anna_meyer, anna))

        with capture_logs() as logs:
            response = await service.analyze(NOVEL, USER)

        assert response.stats.auto_eligible == 1
        assert response.stats.review == 0
        assert response.stats.suppressed == 2
        assert len(response.suggestions) == 1
        assert response.suggestions[0].confidence == pytest.approx(0.895)
        suppressed = [e for e in logs if e["event"] == "resolution_pair_suppressed"]
        assert len(suppressed) == 2
