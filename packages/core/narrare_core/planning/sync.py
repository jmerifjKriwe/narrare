"""Structural sync checker — compares chapter outlines to expected structure.

Pure function with no side effects. Determines whether a chapter's outline
is in sync with the structure adapter's expected stage assignment.

Status priority (first matching rule wins):
  1. EMPTY      — no stage assignment AND no written content
  2. PLANNED    — has stage assignment but no written content
  3. DEVIATED   — stage assignment differs from suggested stage
  4. COMPLETED  — all required planned beats are addressed (content exists)
  5. ON_TRACK   — everything aligned, writing in progress
"""

from __future__ import annotations

from narrare_core.planning.models import ChapterOutlineData, SyncStatus


class StructuralSyncChecker:
    """Determines sync status between a chapter outline and expected structure.

    Stateless — all logic is in the ``calculate_sync_status`` method.
    """

    @staticmethod
    def calculate_sync_status(
        outline: ChapterOutlineData,
        suggested_stage: str,
    ) -> SyncStatus:
        """Return the SyncStatus for *outline* given the *suggested_stage*.

        Parameters
        ----------
        outline:
            The chapter's current outline data.
        suggested_stage:
            The stage ID the structure adapter recommends for this chapter's
            position (from ``adapter.suggest_stage()``).
        """
        # Rule 1: No stage assignment AND no content → EMPTY
        if not outline.stage_assignment and not outline.has_content:
            return SyncStatus.EMPTY

        # Rule 2: Has outline but no content → PLANNED
        if outline.stage_assignment and not outline.has_content:
            return SyncStatus.PLANNED

        # Rule 3: Stage mismatch → DEVIATED
        if outline.stage_assignment != suggested_stage:
            return SyncStatus.DEVIATED

        # Rule 3b: Summary + content → COMPLETED (stronger signal than word count alone)
        if outline.has_summary and outline.has_content:
            return SyncStatus.COMPLETED

        # Rule 4: All required beats addressed → COMPLETED
        required_beats = [b for b in outline.planned_beats if b.required]
        if required_beats and outline.word_count > 0:
            # Heuristic: if content exists and word count is substantial,
            # consider required beats addressed.
            # A more sophisticated check could parse the content for beat markers,
            # but that would require LLM/analysis (outside pure core).
            return SyncStatus.COMPLETED

        # Rule 5: Aligned but still in progress → ON_TRACK
        return SyncStatus.ON_TRACK


__all__ = ["StructuralSyncChecker"]
