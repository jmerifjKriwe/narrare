"""Builders and service factory for ``SeriesJoinService`` unit tests.

Kept out of ``test_join_service.py`` to respect the RULE-04 300-line test
file limit. The fakes themselves live in ``tests/fakes/`` (ADR-030); this
module holds the small test-data factories that wire those fakes together.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from narrare.series.join_service import SeriesJoinService
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry
from tests.fakes.fake_db_session import FakeTxSession
from tests.fakes.fake_kb_join_repo import FakeJoinKBRepo
from tests.fakes.fake_novel_repo import FakeNovelRepository


def overlay_entry(novel_id: UUID, *, entity_type: str, slug: str | None = None) -> NovelKBEntry:
    """Build a Novel-Overlay KB entry (Core type) with sensible defaults."""
    return NovelKBEntry(
        id=uuid4(),
        entity_type=entity_type,
        name=entity_type.title(),
        slug=slug or entity_type,
        novel_id=novel_id,
    )


def canon_entry(series_id: UUID, *, entity_type: str = "system") -> SeriesKBEntry:
    """Build a Series-Canon KB entry (Core type) with sensible defaults."""
    return SeriesKBEntry(
        id=uuid4(),
        entity_type=entity_type,
        name=entity_type.title(),
        slug=f"{entity_type}-canon",
        series_id=series_id,
    )


def seed_mixed_novel(novel_id: UUID, kb_repo: FakeJoinKBRepo) -> list[NovelKBEntry]:
    """Seed one Canon-type + one Overlay-type entry on the novel."""
    entries = [
        overlay_entry(novel_id, entity_type="system"),
        overlay_entry(novel_id, entity_type="character"),
    ]
    kb_repo.seed_overlay(novel_id, entries)
    return entries


def build_service(
    *,
    session: FakeTxSession | None = None,
    novel_repo: FakeNovelRepository | None = None,
    kb_repo: FakeJoinKBRepo | None = None,
) -> tuple[SeriesJoinService, FakeTxSession, FakeNovelRepository, FakeJoinKBRepo]:
    """Assemble a ``SeriesJoinService`` wired to fresh fakes by default.

    ``series_repo`` is injected for DI completeness but unused by the join
    logic, so a minimal stand-in is passed (the service stores it, never
    calls it).
    """
    session = session or FakeTxSession()
    novel_repo = novel_repo or FakeNovelRepository()
    kb_repo = kb_repo or FakeJoinKBRepo()
    service = SeriesJoinService(session, object(), novel_repo, kb_repo)  # type: ignore[arg-type]
    return service, session, novel_repo, kb_repo
