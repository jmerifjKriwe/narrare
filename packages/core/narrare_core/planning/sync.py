"""Structural sync checker — compares chapter outlines to expected structure.

Pure function with no side effects. Determines whether a chapter's outline
is in sync with the structure adapter's expected stage assignment.

Status priority (first matching rule wins):
  1. EMPTY      — no stage assignment AND no written content
  2. PLANNED    — has stage assignment but no written content
  3. DEVIATED   — stage assignment differs from suggested stage
  3b. COMPLETED — summary + content (stronger signal)
  4. COMPLETED  — scene-driven: all scenes COMPLETE and content exists
  5. ON_TRACK   — scenes partially worked, or everything aligned
"""

from __future__ import annotations

from narrare_core.planning.models import ChapterOutlineData, SceneStatus, SyncStatus


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

        # Rule 4 (scene-driven, ADR-096): scenes present ⇒ scene rules
        if outline.scenes:
            if (
                all(s.status is SceneStatus.COMPLETE for s in outline.scenes)
                and outline.has_content
            ):
                return SyncStatus.COMPLETED
            if any(s.status is not SceneStatus.PLANNED for s in outline.scenes):
                return SyncStatus.ON_TRACK

        # Rule 5: Aligned but still in progress → ON_TRACK
        return SyncStatus.ON_TRACK


__all__ = ["StructuralSyncChecker"]
