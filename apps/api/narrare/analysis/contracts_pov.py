"""ANAL-004 POV analysis service contract — POVServiceProtocol.

Split from contracts.py for RULE-04 compliance (< 200 lines).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.analysis.types import POVResult


@runtime_checkable
class POVServiceProtocol(Protocol):
    """Protocol for the ANAL-004 POV analysis service.

    Delegates to a ``POVDetector`` implementation (pydantic-ai agent)
    which handles scene detection, POV character assignment, and
    violation analysis.
    """

    async def analyze(
        self,
        *,
        novel_id: UUID,
        chapter_ids: list[UUID],
        user_id: UUID,
        language: str = "en",
    ) -> POVResult:
        """Analyse POV consistency for the given chapters.

        Args:
            novel_id: The project containing the chapters.
            chapter_ids: Chapters to analyse (concatenated before
                analysis).
            user_id: The user requesting analysis (for access control).
            language: Language override.  If ``"auto"``, resolves from
                the novel's ``writing_language`` setting.
                Defaults to ``"en"``.

        Returns:
            A ``POVResult`` with per-scene assignments, flagged
            violations, and distribution statistics.

        Raises:
            narrare_core.shared.errors.NotFoundError: If a chapter or
                novel does not exist.
            narrare_core.shared.errors.ForbiddenError: If the user
                does not have access.
        """
        ...
