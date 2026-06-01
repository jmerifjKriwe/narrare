"""ANAL-003 Readability service contract — ReadabilityServiceProtocol.

Split from contracts.py for RULE-04 compliance (< 200 lines).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.analysis.types import ReadabilityResult


@runtime_checkable
class ReadabilityServiceProtocol(Protocol):
    """Protocol for the ANAL-003 readability analysis service.

    Orchestrates the deterministic ``ReadabilityAnalyzer`` for
    formula-based metrics and the ``ReadabilityAgentProtocol`` for
    AI-powered sentence analysis.  Results are merged into a single
    ``ReadabilityResult``.
    """

    async def analyze(
        self,
        *,
        novel_id: UUID,
        chapter_ids: list[UUID],
        user_id: UUID,
        language: str = "en",
    ) -> list[ReadabilityResult]:
        """Analyse readability for the given chapters.

        Args:
            novel_id: The project containing the chapters.
            chapter_ids: Chapters to analyse (1-5).
            user_id: The user requesting analysis (for access control).
            language: Language override.  If ``"auto"``, resolves from
                the novel's ``writing_language`` setting.
                Defaults to ``"en"``.

        Returns:
            One ``ReadabilityResult`` per chapter, in the same order
            as ``chapter_ids``.

        Raises:
            narrare_core.shared.errors.NotFoundError: If a chapter or
                novel does not exist.
            narrare_core.shared.errors.ForbiddenError: If the user
                does not have access.
        """
        ...
