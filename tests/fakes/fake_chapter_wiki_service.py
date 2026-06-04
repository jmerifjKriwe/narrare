"""Fake ChapterWikiService for unit tests.

Replaces bare ``MagicMock`` with a programmable fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    import uuid

    from narrare.wiki.schemas import WikiChapterSummaryResponse


class FakeChapterWikiService:
    """Programmable fake for ``ChapterWikiService``."""

    def __init__(self) -> None:
        self.calls: list[CallRecord] = []
        self._return_values: dict[str, Any] = {}

    def configure(self, method: str, return_value: Any) -> None:
        """Set the return value for the next call to *method*."""
        self._return_values[method] = return_value

    async def generate_chapter_summary(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WikiChapterSummaryResponse | None:
        self.calls.append(
            CallRecord(
                "generate_chapter_summary",
                kwargs={
                    "chapter_id": chapter_id,
                    "novel_id": novel_id,
                    "user_id": user_id,
                },
            )
        )
        return self._return_values.pop("generate_chapter_summary", None)

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called_once(self, method: str) -> None:
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_not_called(self, method: str) -> None:
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")
