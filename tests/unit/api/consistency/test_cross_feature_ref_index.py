"""Regression tests for the ADR-050 read-side CrossFeatureRefIndex.

Branch-coverage tests live in ``test_ref_index_branches.py``; shared fakes
and factories are in ``_ref_index_fakes.py`` (extracted for RULE-04).
"""

from __future__ import annotations

from uuid import uuid4

from narrare_core.context.integration_contracts import CrossFeatureRefIndex

from ._ref_index_fakes import (
    FakeChapterRepo as _FakeChapterRepo,
)
from ._ref_index_fakes import (
    FakeKBRepo as _FakeKBRepo,
)
from ._ref_index_fakes import (
    FakeTimelineRepo as _FakeTimelineRepo,
)
from ._ref_index_fakes import (
    make_chapter as _chapter,
)
from ._ref_index_fakes import (
    make_entry as _entry,
)
from ._ref_index_fakes import (
    make_index as _index,
)
from ._ref_index_fakes import (
    make_timeline_event as _timeline_event,
)


class TestProtocol:
    def test_satisfies_core_protocol(self) -> None:
        assert isinstance(_index(_FakeKBRepo()), CrossFeatureRefIndex)


class TestResolveRef:
    async def test_resolve_id_reports_active_deprecated_and_unknown(self) -> None:
        kb = _FakeKBRepo()
        active = _entry(name="John")
        deprecated = _entry(name="Old Castle", status="deprecated")
        kb.seed(active)
        kb.seed(deprecated)
        index = _index(kb)

        assert (
            await index.resolve_ref(novel_id=uuid4(), ref_kind="id", ref_value=str(active.id))
            == "active"
        )
        assert (
            await index.resolve_ref(
                novel_id=uuid4(),
                ref_kind="id",
                ref_value=str(deprecated.id),
            )
            == "deprecated"
        )
        assert (
            await index.resolve_ref(novel_id=uuid4(), ref_kind="id", ref_value=str(uuid4()))
            == "unknown"
        )


class TestTimelineRefs:
    async def test_check_refs_finds_stale_timeline_name_after_missed_rename_event(self) -> None:
        kb = _FakeKBRepo()
        entry = _entry(name="Jonathan")
        kb.seed(entry)
        timeline = _FakeTimelineRepo()
        timeline.seed(_timeline_event(character_refs=[{"id": str(entry.id), "name": "John"}]))
        index = _index(kb, timeline_repo=timeline)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="timeline")

        assert len(issues) == 1
        assert issues[0].reason == "stale_name_ref"
        assert issues[0].resolved_status == "active"

    async def test_check_refs_finds_deleted_timeline_id_after_hard_delete(self) -> None:
        timeline = _FakeTimelineRepo()
        missing_id = uuid4()
        timeline.seed(_timeline_event(character_refs=[{"id": str(missing_id), "name": "John"}]))
        index = _index(_FakeKBRepo(), timeline_repo=timeline)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="timeline")

        assert len(issues) == 1
        assert issues[0].reason == "deleted_ref_without_tombstone"
        assert issues[0].resolved_status == "deleted"


class TestChapterFrontmatterRefs:
    async def test_check_refs_finds_deleted_frontmatter_id(self) -> None:
        chapter_repo = _FakeChapterRepo()
        entity_id = uuid4()
        chapter_repo.seed(_chapter(content=f"---\nlocation: {entity_id}\n---\nBody"))
        index = _index(_FakeKBRepo(), chapter_repo=chapter_repo)

        issues = await index.check_refs(
            novel_id=uuid4(),
            consumer_feature="chapter_frontmatter",
        )

        assert len(issues) == 1
        assert issues[0].consumer_feature == "chapter_frontmatter"
        assert issues[0].reason == "deleted_ref_without_tombstone"
