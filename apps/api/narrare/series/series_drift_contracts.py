"""Contracts for C2 drift persistence (SERIES-004 Slice 6 — RULE-03 first).

Two Protocols fix the persistence surface before any implementation:

- :class:`SeriesDriftRepositoryProtocol` — the ``series_drift_results`` query
  surface. ``store_section`` is an ATOMIC per-section upsert: it merges its
  ``section`` key into the composite JSON document (JSONB ``||``) and
  refreshes the fingerprint + ``generated_at``, so the panel's two parallel
  check POSTs never PK-collide and never clobber each other's section.
- :class:`SeriesDriftPersistenceServiceProtocol` — the wrapper orchestration:
  run a check via the UNCHANGED run services, persist the result, return it
  verbatim; plus the snapshot read with staleness.

Ownership contract (mirrors ``SeriesConsistencyServiceProtocol``):
``get_snapshot`` verifies the caller owns the series AND the novel belongs to
it BEFORE any read; missing/not-owned/non-member ALL surface as
``ForbiddenError`` (HTTP 403, anti-enumeration — never 404). The
``check_and_store_*`` methods inherit verification from the wrapped run
services (they raise before any store happens).

RULE-04: separate file because ``series/contracts.py`` is at its 200-line
limit (``band_summary_contracts.py`` precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.analysis.schemas_author_voice_drift import (
        AuthorVoiceDriftRequest,
        AuthorVoiceDriftResponse,
    )
    from narrare.series.series_consistency_schemas import (
        SeriesConsistencyCheckResponse,
    )
    from narrare.series.series_drift_models import SeriesDriftResult
    from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse

DriftSection = Literal["consistency", "voice_drift"]
"""The two composite-document keys — one per check run."""


@runtime_checkable
class SeriesDriftRepositoryProtocol(Protocol):
    """Query surface for the ``series_drift_results`` table (1:1 to Novel)."""

    async def get(self, novel_id: uuid.UUID) -> SeriesDriftResult | None:
        """Load the persisted snapshot row for a novel (``None`` if none)."""
        ...

    async def store_section(
        self,
        novel_id: uuid.UUID,
        *,
        section: DriftSection,
        document: dict[str, object],
        fingerprint: str,
    ) -> None:
        """Atomically upsert ONE section of the composite document.

        Merges ``document`` under ``result[section]`` (JSONB shallow merge),
        sets ``input_fingerprint`` to the save-time fingerprint, and refreshes
        record-level ``generated_at``. Safe under concurrency (ON CONFLICT).
        """
        ...


@runtime_checkable
class SeriesDriftPersistenceServiceProtocol(Protocol):
    """Run-then-persist orchestration + snapshot read (C2)."""

    async def check_and_store_consistency(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesConsistencyCheckResponse:
        """Run the canon-contradiction check, persist its section, return it.

        Delegates to the UNCHANGED ``SeriesConsistencyService.check_novel``
        (ownership + membership verified there — a 403 raises BEFORE any
        store). The response is returned verbatim even when the store write
        degrades (RULE-11 — see the service docstring).
        """
        ...

    async def check_and_store_voice_drift(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AuthorVoiceDriftResponse:
        """Run the series-voice-drift check, persist its section, return it.

        Same contract as :meth:`check_and_store_consistency`, delegating to
        the UNCHANGED ``SeriesVoiceDriftService.check``.
        """
        ...

    async def get_snapshot(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesDriftSnapshotResponse:
        """Read the persisted snapshot with the staleness flag.

        Recomputes the current chapter-texts fingerprint and compares it with
        the stored one: ``stale=True`` means the band's texts changed since
        the last completed write. No record → all-null snapshot with
        ``stale=False`` (never an error). Missing/not-owned series and
        non-member novel → ``ForbiddenError`` (403, anti-enumeration).
        """
        ...
