"""Resolution analysis service for the KB entity resolution layer (ADR-085 P3).

Orchestrates the detection pass (spec §7): snapshots (via the injected
builder) are fed through the pure ``ResolutionEngine`` and mapped to
banded suggestions with per-signal evidence. ``SUPPRESSED`` pairs are
counted and info-logged (RULE-11 — never silently dropped) but never
surfaced. Suggestion identity is stateless (``sha256(min ‖ max)[:16]``
over the entry-id strings) so endorsements can be re-validated later
without a suggestion table.

Caching mirrors the ``kb/consistency_cache.py`` pattern — injected
``SessionCacheProtocol`` backend, 10-minute TTL, novel-scoped key,
tolerant reads — with one deviation: the entries hash is stored in an
envelope next to the payload instead of being appended to the key.
Root cause: a fresh hash suffix per KB mutation would strand one TTL key
per mutation and make an explicit ``invalidate`` impossible to enumerate
(a hash-suffixed key for a *previous* entry set cannot be derived after
the mutation). The envelope binds the cached payload to the entry set
with the same staleness safety while ``delete_all`` remains a real
single-key invalidation for the KB-mutation hooks wired in later tasks.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Final, cast

import structlog

from narrare.kb.entity_resolution.schemas_resolution import (
    BandStats,
    ResolutionAnalysisResponse,
    SignalEvidence,
    SuggestionResponse,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from uuid import UUID

    from narrare.kb.entity_resolution.contracts import SnapshotBuilderProtocol
    from narrare.kb.entity_resolution.schemas_resolution import SuggestionBand
    from narrare_core.kb.resolution.models import EntitySnapshot, PairScore
    from narrare_core.kb.resolution.scoring import ResolutionEngine
    from narrare_core.writing.session_manager import SessionCacheProtocol

logger = structlog.get_logger(__name__)

_DEFAULT_TTL_SECONDS: Final[int] = 600
_DEFAULT_KEY_PREFIX: Final[str] = "kb:resolution:"


def _entries_hash(snapshots: Sequence[EntitySnapshot]) -> str:
    """Derive the stable 8-char digest binding a cached analysis to its inputs.

    Snapshots are digested in ``str(entry_id)`` order regardless of builder
    ordering; every field the engine consumes (name, type, status, metadata,
    provenance chapters/variants, neighbor ids, embedding) participates, so
    any KB mutation that could change the analysis changes the hash.
    """
    digest = hashlib.sha256()
    for snapshot in sorted(snapshots, key=lambda s: str(s.entry_id)):
        provenance = snapshot.provenance
        digest.update(
            json.dumps(
                {
                    "id": str(snapshot.entry_id),
                    "name": snapshot.name,
                    "entity_type": snapshot.entity_type,
                    "status": snapshot.status,
                    "metadata": snapshot.metadata,
                    "provenance": None
                    if provenance is None
                    else [list(provenance.chapters), list(provenance.name_variants)],
                    "neighbors": sorted(str(n) for n in snapshot.neighbor_ids),
                    "embedding": (
                        list(snapshot.embedding) if snapshot.embedding is not None else None
                    ),
                },
                sort_keys=True,
                default=str,
            ).encode()
        )
    return digest.hexdigest()[:8]


class ResolutionAnalysisCache:
    """Cache for resolution analysis results (in-memory backend per ADR-080).

    Single key per novel (``kb:resolution:{novel_id}``) holding a
    ``{"entries_hash": str, "payload": str}`` envelope; a lookup is a hit
    only when the stored hash matches the caller's current entries hash.

    Args:
        cache: Injected cache backend via ``SessionCacheProtocol``.
        ttl: Cache TTL in seconds.
        key_prefix: Cache key prefix for namespace isolation.
    """

    def __init__(
        self,
        cache: SessionCacheProtocol,
        *,
        ttl: int = _DEFAULT_TTL_SECONDS,
        key_prefix: str = _DEFAULT_KEY_PREFIX,
    ) -> None:
        self._cache = cache
        self._ttl = ttl
        self._key_prefix = key_prefix

    def _key(self, novel_id: str) -> str:
        return f"{self._key_prefix}{novel_id}"

    async def get(self, novel_id: str, entries_hash: str) -> str | None:
        """Return the cached payload iff it was stored for ``entries_hash``.

        Backend failures and malformed envelopes degrade to a miss
        (fails open — recomputation is always correct, RULE-11).
        """
        try:
            raw = await self._cache.get(self._key(novel_id))
            envelope = cast(
                "dict[str, object] | None",
                json.loads(raw) if raw is not None else None,
            )
        except Exception:
            logger.warning("resolution_cache_unavailable", novel_id=novel_id)
            return None
        if not isinstance(envelope, dict) or envelope.get("entries_hash") != entries_hash:
            return None
        payload = envelope.get("payload")
        if not isinstance(payload, str):
            logger.warning("resolution_cache_malformed", novel_id=novel_id)
            return None
        logger.debug("resolution_cache_hit", novel_id=novel_id)
        return payload

    async def set(self, novel_id: str, value: str, entries_hash: str) -> None:
        """Cache the analysis payload bound to ``entries_hash`` with the TTL."""
        envelope = json.dumps({"entries_hash": entries_hash, "payload": value})
        await self._cache.set(self._key(novel_id), envelope, ttl_seconds=self._ttl)
        logger.debug("resolution_cache_set", novel_id=novel_id)

    async def delete_all(self, novel_id: str) -> None:
        """Invalidate the cached analysis for a novel (KB-mutation hook point)."""
        await self._cache.delete(self._key(novel_id))
        logger.debug("resolution_cache_invalidated", novel_id=novel_id)


class ResolutionAnalysisService:
    """Detection pass: snapshots → engine → banded suggestions (+ cache).

    Implements :class:`~narrare.kb.entity_resolution.contracts.ResolutionAnalyzerProtocol`.
    Dependencies are injected (RULE-19): the snapshot builder, the pure
    scoring engine, and the analysis cache. Stateless w.r.t. suggestion
    identity — the same entry pair always yields the same suggestion id.
    """

    def __init__(
        self,
        builder: SnapshotBuilderProtocol,
        engine: ResolutionEngine,
        cache: ResolutionAnalysisCache,
    ) -> None:
        self._builder = builder
        self._engine = engine
        self._cache = cache

    async def analyze(
        self,
        novel_id: UUID,
        user_id: UUID,
        *,
        refresh: bool = False,
    ) -> ResolutionAnalysisResponse:
        """Run (or fetch) the duplicate detection analysis for one novel.

        Args:
            novel_id: The novel scope to analyze.
            user_id: Authenticated user triggering the analysis (audit log).
            refresh: Skip the cache read and force a recompute.

        Returns:
            The surfaced suggestions, per-band stats, and cache status.
        """
        novel_str = str(novel_id)
        snapshots = await self._builder.build(novel_id)
        entries_hash = _entries_hash(snapshots)

        if not refresh:
            cached = await self._cache.get(novel_str, entries_hash)
            if cached is not None:
                response = ResolutionAnalysisResponse.model_validate_json(cached)
                return response.model_copy(update={"cache_hit": True})

        names: Mapping[UUID, str] = {s.entry_id: s.name for s in snapshots}
        suggestions: list[SuggestionResponse] = []
        review = auto_eligible = suppressed = 0
        for a, b in self._engine.find_candidates(snapshots):
            score = self._engine.score_pair(a, b)
            band = score.band
            if band == "SUPPRESSED":
                suppressed += 1
                logger.info(
                    "resolution_pair_suppressed",
                    novel_id=novel_str,
                    entry_a_id=str(score.entry_a_id),
                    entry_b_id=str(score.entry_b_id),
                    confidence=score.confidence,
                    vetoes=list(score.vetoes),
                )
                continue
            suggestions.append(self._to_suggestion(score, names, band))
            if band == "AUTO_ELIGIBLE":
                auto_eligible += 1
            else:
                review += 1

        response = ResolutionAnalysisResponse(
            suggestions=suggestions,
            stats=BandStats(review=review, auto_eligible=auto_eligible, suppressed=suppressed),
            cache_hit=False,
        )
        await self._cache.set(novel_str, response.model_dump_json(), entries_hash)
        logger.info(
            "resolution_analysis_complete",
            novel_id=novel_str,
            user_id=str(user_id),
            suggestions=len(suggestions),
            review=review,
            auto_eligible=auto_eligible,
            suppressed=suppressed,
        )
        return response

    async def get_cached(self, novel_id: UUID) -> ResolutionAnalysisResponse:
        """Return the cached analysis WITHOUT recomputing (spec §7 GET suggestions).

        The cache payload is validated against the current entries hash, so
        reading it requires building snapshots — a read-only KB fetch, not a
        detection recompute (the engine never runs here). A miss (never
        analyzed, invalidated, or stale after a KB mutation) yields the empty
        response with ``cache_hit=False`` — the endpoint is 404-free (§7).
        """
        snapshots = await self._builder.build(novel_id)
        cached = await self._cache.get(str(novel_id), _entries_hash(snapshots))
        if cached is None:
            return ResolutionAnalysisResponse(
                suggestions=[],
                stats=BandStats(review=0, auto_eligible=0, suppressed=0),
                cache_hit=False,
            )
        response = ResolutionAnalysisResponse.model_validate_json(cached)
        return response.model_copy(update={"cache_hit": True})

    async def invalidate(self, novel_id: UUID) -> None:
        """Drop the cached analysis for a novel.

        KB-mutation flows call this in later tasks so the next analysis
        never serves a pre-mutation result (spec §7 invalidation clause).
        """
        await self._cache.delete_all(str(novel_id))

    @staticmethod
    def _to_suggestion(
        score: PairScore,
        names: Mapping[UUID, str],
        band: SuggestionBand,
    ) -> SuggestionResponse:
        """Map one non-suppressed ``PairScore`` to its response schema.

        ``band`` is passed pre-narrowed (``SUPPRESSED`` never reaches this
        mapper — the caller filters and counts those pairs first).
        """
        id_a, id_b = str(score.entry_a_id), str(score.entry_b_id)
        lo, hi = min(id_a, id_b), max(id_a, id_b)
        return SuggestionResponse(
            suggestion_id=hashlib.sha256(f"{lo}{hi}".encode()).hexdigest()[:16],
            entry_a_id=score.entry_a_id,
            entry_b_id=score.entry_b_id,
            name_a=names[score.entry_a_id],
            name_b=names[score.entry_b_id],
            confidence=score.confidence,
            band=band,
            auto_merge_eligible=band == "AUTO_ELIGIBLE",
            signals=[
                SignalEvidence(signal=s.signal, value=s.value, veto=s.veto, detail=s.detail)
                for s in score.signals
            ],
        )
