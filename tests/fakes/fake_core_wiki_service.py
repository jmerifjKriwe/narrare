"""Fake core WikiService for unit tests.

Replaces bare ``MagicMock`` with an in-memory implementation
for ``WikiServiceProtocol`` (core layer).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    from narrare_core.wiki.types import (
        WikiChapterOutput,
        WikiEntityOutput,
        WikiGenerationDeps,
        WikiSummaryData,
    )


class FakeCoreWikiService:
    """In-memory fake for ``WikiServiceProtocol``.

    Returns configurable ``WikiEntityOutput`` / ``WikiChapterOutput``
    via the ``configure()`` method.
    """

    def __init__(self) -> None:
        self.calls: list[CallRecord] = []
        self._return_values: dict[str, Any] = {}

    def configure(self, method: str, return_value: Any) -> None:
        """Set the return value for the next call to *method*."""
        self._return_values[method] = return_value

    async def generate_entity_summary(
        self,
        entity_id: str,
        novel_id: str,
        deps: WikiGenerationDeps | None = None,
    ) -> WikiEntityOutput | None:
        self.calls.append(
            CallRecord(
                "generate_entity_summary",
                kwargs={"entity_id": entity_id, "novel_id": novel_id},
            )
        )
        return self._return_values.pop("generate_entity_summary", None)

    async def get_summaries(
        self,
        entity_ids: list[str],
        novel_id: str,
    ) -> dict[str, WikiSummaryData]:
        self.calls.append(CallRecord("get_summaries"))
        return {}

    async def refresh_summary(
        self,
        entity_id: str,
        novel_id: str,
    ) -> WikiEntityOutput | None:
        self.calls.append(CallRecord("refresh_summary"))
        return None

    async def mark_all_stale(
        self,
        novel_id: str,
        prompt_version: str | None = None,
    ) -> int:
        self.calls.append(CallRecord("mark_all_stale"))
        return 0

    async def generate_chapter(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiChapterOutput | None:
        self.calls.append(CallRecord("generate_chapter"))
        return self._return_values.pop("generate_chapter", None)

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
