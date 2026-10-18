"""M11 wire half: the wiki summaries list carries the KB entity NAME.

The overview card previously had only ``entity_id`` (a raw UUID) to render
(audit M11). ``list_summaries`` enriches each item from one batched KB read
via ``list_entries`` — ``None`` for entries that no longer exist.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from narrare.kb.models import KBEntry
from narrare.wiki.generation_support import list_summaries
from narrare.wiki.models import WikiSummary
from tests.fakes import FakeKBRepository, FakeWikiRepository
from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.wiki.repository import WikiRepository


class ListEntriesKBRepository(FakeKBRepository):
    """FakeKBRepository whose ``list_entries`` serves the given entries.

    The canonical fake returns empty pages (it has no seeded page store);
    enrichment needs a KB read that yields the novel's entities.
    """

    def __init__(self, entries: list[KBEntry]) -> None:
        super().__init__()
        self._entries = entries

    async def list_entries(
        self,
        novel_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KBEntry], int]:
        self.calls.append(CallRecord("list_entries"))
        entries = [e for e in self._entries if e.novel_id == novel_id]
        return entries, len(entries)


def _summary_row(entity_id: uuid.UUID, novel_id: uuid.UUID) -> WikiSummary:
    return WikiSummary(
        id=uuid.uuid4(),
        novel_id=novel_id,
        entity_id=entity_id,
        narrative_summary="Keeps her mother's ring.",
        role_in_story="Protagonist",
        key_attributes=["resolute"],
        relationships=None,
        chapter_references=None,
        character_arc=None,
        status="fresh",
        version=1,
        generated_at=datetime(2026, 10, 15, tzinfo=UTC),
        refreshed_at=datetime(2026, 10, 15, tzinfo=UTC),
    )


def _entity(entity_id: uuid.UUID, novel_id: uuid.UUID, name: str) -> KBEntry:
    return KBEntry(
        id=entity_id,
        novel_id=novel_id,
        entity_type="character",
        name=name,
        body="A determined heir.",
    )


async def test_list_summaries_enriches_entity_name() -> None:
    novel_id, entity_id = uuid.uuid4(), uuid.uuid4()
    wiki_repo = FakeWikiRepository()
    wiki_repo.seed_summaries(_summary_row(entity_id, novel_id))
    kb_repo = ListEntriesKBRepository([_entity(entity_id, novel_id, "Elara Thornwind")])

    result = await list_summaries(
        cast("WikiRepository", wiki_repo),
        cast("KBRepositoryProtocol", kb_repo),
        None,
        novel_id,
    )

    assert result.total == 1
    assert result.items[0].entity_name == "Elara Thornwind"


async def test_list_summaries_name_none_for_missing_entry() -> None:
    novel_id = uuid.uuid4()
    wiki_repo = FakeWikiRepository()
    wiki_repo.seed_summaries(_summary_row(uuid.uuid4(), novel_id))
    kb_repo = ListEntriesKBRepository([])  # no entries -> no names

    result = await list_summaries(
        cast("WikiRepository", wiki_repo),
        cast("KBRepositoryProtocol", kb_repo),
        None,
        novel_id,
    )

    assert result.total == 1
    assert result.items[0].entity_name is None
