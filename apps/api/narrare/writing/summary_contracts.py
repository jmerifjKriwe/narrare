"""Protocols for chapter summary service.

Defines the contract (RULE-03) that ChapterSummaryService implements.
Every method is async, every result is typed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class SummaryResult:
    """Result of a chapter summarization operation.

    Attributes:
        summary: The generated summary text.
        word_count: Word count of the summary.
        key_points: Key narrative points extracted from the chapter.
    """

    summary: str = ""
    word_count: int = 0
    key_points: list[str] = field(default_factory=list[str])


class SummaryServiceProtocol(Protocol):
    """Contract for chapter summary service.

    Any implementation must fulfill this interface (RULE-03).
    """

    async def summarize(
        self,
        chapter_id: UUID,
        max_sentences: int = 4,
        language: str = "en",
        *,
        user_id: str,
    ) -> SummaryResult:
        """Generate a summary for the given chapter.

        Ownership gate (IDOR remediation S4, Pattern B): the chapter's
        novel must belong to ``user_id`` BEFORE any content load, LLM
        call, or ``update_summary`` write.  Foreign and unknown chapter
        ids are indistinguishable (both raise ``NotFoundError``).

        Args:
            chapter_id: The UUID of the chapter to summarize.
            max_sentences: Maximum number of sentences in the summary.
            language: Output language code (default "en").
            user_id: Authenticated user identifier (ownership check).

        Returns:
            SummaryResult with summary text, word count, and key points.

        Raises:
            NotFoundError: If the chapter does not exist or its novel
                belongs to another user.
            WritingError: If the LLM call fails.
        """
        ...
