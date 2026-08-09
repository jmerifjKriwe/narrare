"""Fake wiki repository for unit tests.

Replaces bare ``MagicMock`` with an in-memory implementation
that stores ``WikiSummary`` and ``WikiChapterSummary`` data.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    from narrare.wiki.models import WikiChapterSummary, WikiSummary
    from narrare_core.wiki.types import (
        WikiChapterOutput,
        WikiChapterSummaryData,
        WikiEntityOutput,
        WikiSummaryData,
    )


class FakeWikiRepository:
    """In-memory fake for ``WikiRepository``.

    Stores summaries keyed by ``(entity_id, novel_id)`` for entity
    summaries and by ``chapter_id`` for chapter summaries.
    """

    def __init__(self) -> None:
        self._entity_summaries: dict[tuple[uuid.UUID, uuid.UUID], WikiSummary] = {}
        self._chapter_summaries: dict[uuid.UUID, WikiChapterSummary] = {}
        self.calls: list[CallRecord] = []
        self._return_values: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Configuration for tests that need precise return-value control
    # ------------------------------------------------------------------

    def configure(self, method: str, return_value: Any) -> None:
        """Configure a custom return value for the next call to *method*."""
        self._return_values[method] = return_value

    # ------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------

    async def upsert_summary(
        self,
        summary_data: WikiSummaryData,
        output: WikiEntityOutput,
    ) -> WikiSummary:
        self.calls.append(CallRecord("upsert_summary"))
        if "upsert_summary" in self._return_values:
            return self._return_values.pop("upsert_summary")  # type: ignore[return-value]

        from narrare.wiki.models import WikiSummary

        summary = WikiSummary(
            id=uuid.uuid4(),
            novel_id=uuid.UUID(summary_data.novel_id),
            entity_id=uuid.UUID(summary_data.entity_id),
            narrative_summary=output.narrative_summary,
            role_in_story=output.role_in_story,
            key_attributes=output.key_attributes or None,
            relationships=output.relationships or None,
            character_arc=output.character_arc,
            status=summary_data.status.value,
            version=summary_data.version,
        )
        key = (uuid.UUID(summary_data.entity_id), uuid.UUID(summary_data.novel_id))
        self._entity_summaries[key] = summary
        return summary

    async def get_summary(self, entity_id: uuid.UUID, novel_id: uuid.UUID) -> WikiSummary | None:
        self.calls.append(
            CallRecord("get_summary", kwargs={"entity_id": entity_id, "novel_id": novel_id})
        )
        if "get_summary" in self._return_values:
            return self._return_values.pop("get_summary")

        return self._entity_summaries.get((entity_id, novel_id))

    async def get_summaries(
        self,
        entity_ids: list[uuid.UUID] | None,
        novel_id: uuid.UUID,
    ) -> list[WikiSummary]:
        self.calls.append(
            CallRecord("get_summaries", kwargs={"entity_ids": entity_ids, "novel_id": novel_id})
        )
        if "get_summaries" in self._return_values:
            return self._return_values.pop("get_summaries")

        summaries = [s for (_, nid), s in self._entity_summaries.items() if nid == novel_id]
        if entity_ids is not None:
            summaries = [s for s in summaries if s.entity_id in entity_ids]
        return summaries

    async def upsert_chapter_summary(
        self,
        chapter_summary_data: WikiChapterSummaryData,
        output: WikiChapterOutput,
    ) -> WikiChapterSummary:
        self.calls.append(CallRecord("upsert_chapter_summary"))
        if "upsert_chapter_summary" in self._return_values:
            return self._return_values.pop("upsert_chapter_summary")

        from narrare.wiki.models import WikiChapterSummary

        summary = WikiChapterSummary(
            chapter_id=uuid.UUID(chapter_summary_data.chapter_id),
            narrative_summary=output.narrative_summary,
            key_events=output.key_events or None,
            entities_involved=output.entities_involved or None,
            themes=output.themes or None,
            emotional_arc=output.emotional_arc,
            status=chapter_summary_data.status.value,
            version=chapter_summary_data.version,
        )
        self._chapter_summaries[summary.chapter_id] = summary
        return summary

    async def get_chapter_summary(self, chapter_id: uuid.UUID) -> WikiChapterSummary | None:
        self.calls.append(CallRecord("get_chapter_summary", kwargs={"chapter_id": chapter_id}))
        if "get_chapter_summary" in self._return_values:
            return self._return_values.pop("get_chapter_summary")

        return self._chapter_summaries.get(chapter_id)

    async def mark_stale(self, entity_ids: list[uuid.UUID]) -> int:
        self.calls.append(CallRecord("mark_stale", kwargs={"entity_ids": entity_ids}))
        count = 0
        for (eid, _nid), summary in list(self._entity_summaries.items()):
            if eid in entity_ids:
                summary.status = "stale"
                count += 1
        return count

    async def mark_all_stale(
        self,
        novel_id: uuid.UUID,
        current_prompt_version: str,
    ) -> int:
        self.calls.append(
            CallRecord(
                "mark_all_stale",
                kwargs={"novel_id": novel_id, "prompt_version": current_prompt_version},
            )
        )
        if "mark_all_stale" in self._return_values:
            return self._return_values.pop("mark_all_stale")

        count = 0
        for (_eid, nid), summary in self._entity_summaries.items():
            if nid == novel_id:
                summary.status = "stale"
                count += 1
        return count

    async def mark_related_stale(self, entity_id: uuid.UUID) -> int:
        self.calls.append(CallRecord("mark_related_stale", kwargs={"entity_id": entity_id}))
        if "mark_related_stale" in self._return_values:
            return self._return_values.pop("mark_related_stale")
        return 0

    async def mark_all_stale_global(self) -> int:
        """Mirror ``WikiRepository.mark_all_stale_global`` (Q-016)."""
        self.calls.append(CallRecord("mark_all_stale_global"))
        if "mark_all_stale_global" in self._return_values:
            return self._return_values.pop("mark_all_stale_global")
        count = 0
        for summary in self._entity_summaries.values():
            summary.status = "stale"
            count += 1
        return count

    async def delete_summary(self, entity_id: uuid.UUID) -> None:
        self.calls.append(CallRecord("delete_summary", kwargs={"entity_id": entity_id}))
        keys = [k for k in self._entity_summaries if k[0] == entity_id]
        for k in keys:
            del self._entity_summaries[k]

    # ------------------------------------------------------------------
    # Helper: seed pre-existing data
    # ------------------------------------------------------------------

    def seed_summaries(self, *summaries: WikiSummary) -> None:
        """Pre-populate entity summaries."""
        for s in summaries:
            self._entity_summaries[(s.entity_id, s.novel_id)] = s

    def seed_chapter_summaries(self, *summaries: WikiChapterSummary) -> None:
        """Pre-populate chapter summaries."""
        for s in summaries:
            self._chapter_summaries[s.chapter_id] = s

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
