"""BandSummary repository contract (Spec 2 — Series Generation Context, Task 3).

A separate Protocol file (not appended to ``series/contracts.py``) so the
existing 197-line ``contracts.py`` stays under the RULE-04 file-size limit and
band-summary concerns stay self-contained (RULE-06: one responsibility per
file). Mirrors the ``kb/scope_contracts.py`` extraction precedent.

``BandSummaryRepositoryProtocol`` is the DB-query surface used by
``BandSummaryService`` (Task 3) and by ``SeriesHistoryTier`` (Task 6, via the
service). The concrete implementation lives in ``band_summary_repository.py``.

The 1:1 invariant (one summary row per novel, enforced by ``BandSummary``'s
``novel_id`` PK+UNIQUE — see ``band_summary_models.py``) means every mutating
method is an upsert: a missing row is created on demand, an existing row is
patched in place. ``set_override`` / ``clear_override`` are split (rather than
one ``override=None`` path) so the service can express intent explicitly and
the repository keeps a single mutation primitive per column concern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.series.band_summary_models import BandSummary


@runtime_checkable
class BandSummaryRepositoryProtocol(Protocol):
    """DB-query surface for the ``band_summaries`` table (1:1 to ``Novel``).

    All mutating methods upsert: they load the row by ``novel_id`` (the PK) and
    create it if absent, so callers never need to pre-check existence. The
    returned ``BandSummary`` always reflects the post-mutation state with
    server-defaults (``generated_at``) loaded.
    """

    async def get(self, novel_id: uuid.UUID) -> BandSummary | None:
        """Load the band summary for a novel (``None`` if no row yet)."""
        ...

    async def upsert(
        self,
        novel_id: uuid.UUID,
        full_summary: str,
        short_summary: str,
    ) -> BandSummary:
        """Insert or update ``full_summary`` + ``short_summary`` for a novel.

        Used by the generation pipeline after a successful ``BandSummaryAgent``
        run. ``override`` (if any) is preserved untouched.
        """
        ...

    async def set_override(self, novel_id: uuid.UUID, override: str) -> BandSummary:
        """Set the user ``override`` for a novel (creates row on demand).

        The override takes precedence over generated text at assembly time
        (Spec 2 Task 6 ``SeriesHistoryTier``).
        """
        ...

    async def clear_override(self, novel_id: uuid.UUID) -> BandSummary:
        """Clear the user ``override`` for a novel (creates row on demand).

        Idempotent: clearing a non-existent or already-clear row still returns
        a row with ``override is None``.
        """
        ...
