"""Branch-coverage tests for the ADR-050 read-side CrossFeatureRefIndex.

Covers the dispatch, resolve_ref name/non-uuid paths, timeline location_ref
and hybrid-ref edges, storyboard deprecated-name detection, and the full
scalar-ref decision tree. Shared fakes live in ``_ref_index_fakes.py``.
"""

from __future__ import annotations

from uuid import uuid4

from ._ref_index_fakes import (
    FakeChapterRepo,
    FakeKBRepo,
    FakeOutlineRepo,
    FakeTimelineRepo,
    make_chapter,
    make_entry,
    make_index,
    make_outline,
    make_timeline_event,
)


class TestCheckRefsDispatch:
    async def test_unknown_consumer_feature_returns_empty(self) -> None:
        index = make_index(FakeKBRepo())
        assert await index.check_refs(novel_id=uuid4(), consumer_feature="unknown") == []

    async def test_storyboard_dispatch_with_no_outlines_returns_empty(self) -> None:
        index = make_index(FakeKBRepo())
        assert await index.check_refs(novel_id=uuid4(), consumer_feature="storyboard") == []


class TestResolveRefBranches:
    async def test_resolve_id_with_non_uuid_value_returns_unknown(self) -> None:
        index = make_index(FakeKBRepo())
        assert (
            await index.resolve_ref(novel_id=uuid4(), ref_kind="id", ref_value="legacy-name")
            == "unknown"
        )

    async def test_resolve_name_reports_active_and_unknown(self) -> None:
        kb = FakeKBRepo()
        kb.seed(make_entry(name="John"))
        index = make_index(kb)
        assert (
            await index.resolve_ref(novel_id=uuid4(), ref_kind="name", ref_value="John") == "active"
        )
        assert (
            await index.resolve_ref(novel_id=uuid4(), ref_kind="name", ref_value="Nobody")
            == "unknown"
        )

    async def test_resolve_name_reports_deprecated(self) -> None:
        kb = FakeKBRepo()
        kb.seed(make_entry(name="OldCastle", status="deprecated"))
        index = make_index(kb)
        assert (
            await index.resolve_ref(novel_id=uuid4(), ref_kind="name", ref_value="OldCastle")
            == "deprecated"
        )


class TestTimelineLocationRef:
    async def test_location_ref_deleted_id_is_reported(self) -> None:
        timeline = FakeTimelineRepo()
        missing = uuid4()
        timeline.seed(make_timeline_event(location_ref={"id": str(missing), "name": "Tavern"}))
        index = make_index(FakeKBRepo(), timeline_repo=timeline)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="timeline")

        assert len(issues) == 1
        assert issues[0].reason == "deleted_ref_without_tombstone"
        assert "location_ref" in issues[0].consumer_location


class TestTimelineHybridRefEdges:
    async def test_non_string_ref_id_produces_no_issue(self) -> None:
        timeline = FakeTimelineRepo()
        timeline.seed(make_timeline_event(character_refs=[{"id": 123}]))  # type: ignore[dict-item]
        index = make_index(FakeKBRepo(), timeline_repo=timeline)
        assert await index.check_refs(novel_id=uuid4(), consumer_feature="timeline") == []

    async def test_non_uuid_legacy_ref_id_produces_no_issue(self) -> None:
        timeline = FakeTimelineRepo()
        timeline.seed(make_timeline_event(character_refs=[{"id": "legacy-name", "name": "x"}]))
        index = make_index(FakeKBRepo(), timeline_repo=timeline)
        assert await index.check_refs(novel_id=uuid4(), consumer_feature="timeline") == []

    async def test_deprecated_timeline_ref_is_reported(self) -> None:
        kb = FakeKBRepo()
        deprecated = make_entry(name="OldHero", status="deprecated")
        kb.seed(deprecated)
        timeline = FakeTimelineRepo()
        timeline.seed(
            make_timeline_event(character_refs=[{"id": str(deprecated.id), "name": "OldHero"}])
        )
        index = make_index(kb, timeline_repo=timeline)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="timeline")

        assert len(issues) == 1
        assert issues[0].resolved_status == "deprecated"
        assert issues[0].reason == "deprecated_ref_in_active_context"


class TestStoryboardRefs:
    async def test_deprecated_name_in_beat_text_is_warned(self) -> None:
        kb = FakeKBRepo()
        kb.seed(make_entry(name="Oldcastle", status="deprecated"))
        outlines = FakeOutlineRepo()
        outlines.seed(make_outline(planned_beats=[{"text": "They march on Oldcastle at dawn."}]))
        index = make_index(kb, outline_repo=outlines)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="storyboard")

        assert len(issues) == 1
        assert issues[0].consumer_feature == "storyboard"
        assert issues[0].ref_value == "Oldcastle"
        assert issues[0].suggested_action == "warn_only"

    async def test_deprecated_name_in_outline_notes_is_warned(self) -> None:
        kb = FakeKBRepo()
        kb.seed(make_entry(name="Ruinfell", status="deprecated"))
        outlines = FakeOutlineRepo()
        outlines.seed(make_outline(outline_notes="Recall the fall of Ruinfell."))
        index = make_index(kb, outline_repo=outlines)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="storyboard")

        assert len(issues) == 1
        assert issues[0].ref_value == "Ruinfell"

    async def test_active_name_in_storyboard_produces_no_issue(self) -> None:
        kb = FakeKBRepo()
        kb.seed(make_entry(name="Activeville"))
        outlines = FakeOutlineRepo()
        outlines.seed(make_outline(planned_beats=[{"text": "Visit Activeville soon."}]))
        index = make_index(kb, outline_repo=outlines)
        assert await index.check_refs(novel_id=uuid4(), consumer_feature="storyboard") == []

    async def test_whitespace_only_storyboard_text_produces_no_issue(self) -> None:
        outlines = FakeOutlineRepo()
        outlines.seed(make_outline(planned_beats=[{"text": "    "}]))
        index = make_index(FakeKBRepo(), outline_repo=outlines)
        assert await index.check_refs(novel_id=uuid4(), consumer_feature="storyboard") == []


class TestChapterFrontmatterScalarBranches:
    async def test_deprecated_frontmatter_id_is_marked(self) -> None:
        kb = FakeKBRepo()
        deprecated = make_entry(name="OldGod", status="deprecated")
        kb.seed(deprecated)
        chapter_repo = FakeChapterRepo()
        chapter_repo.seed(make_chapter(content=f"---\nlocation: {deprecated.id}\n---\nBody"))
        index = make_index(kb, chapter_repo=chapter_repo)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="chapter_frontmatter")

        assert len(issues) == 1
        assert issues[0].resolved_status == "deprecated"
        assert issues[0].suggested_action == "mark_deprecated_in_context"

    async def test_active_frontmatter_id_produces_no_issue(self) -> None:
        kb = FakeKBRepo()
        active = make_entry(name="Sunhaven")
        kb.seed(active)
        chapter_repo = FakeChapterRepo()
        chapter_repo.seed(make_chapter(content=f"---\nlocation: {active.id}\n---\nBody"))
        index = make_index(kb, chapter_repo=chapter_repo)
        assert (
            await index.check_refs(novel_id=uuid4(), consumer_feature="chapter_frontmatter") == []
        )

    async def test_unknown_frontmatter_name_is_warned(self) -> None:
        chapter_repo = FakeChapterRepo()
        chapter_repo.seed(make_chapter(content="---\nlocation: Nowhere\n---\nBody"))
        index = make_index(FakeKBRepo(), chapter_repo=chapter_repo)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="chapter_frontmatter")

        assert len(issues) == 1
        assert issues[0].resolved_status == "unknown"
        assert issues[0].ref_value == "Nowhere"
        assert issues[0].suggested_action == "warn_only"

    async def test_deprecated_frontmatter_name_is_marked(self) -> None:
        kb = FakeKBRepo()
        kb.seed(make_entry(name="Doomspire", status="deprecated"))
        chapter_repo = FakeChapterRepo()
        chapter_repo.seed(make_chapter(content="---\nlocation: Doomspire\n---\nBody"))
        index = make_index(kb, chapter_repo=chapter_repo)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="chapter_frontmatter")

        assert len(issues) == 1
        assert issues[0].resolved_status == "deprecated"
        assert issues[0].reason == "deprecated_ref_in_active_context"

    async def test_active_frontmatter_name_produces_no_issue(self) -> None:
        kb = FakeKBRepo()
        kb.seed(make_entry(name="Sunhaven"))
        chapter_repo = FakeChapterRepo()
        chapter_repo.seed(make_chapter(content="---\nlocation: Sunhaven\n---\nBody"))
        index = make_index(kb, chapter_repo=chapter_repo)
        assert (
            await index.check_refs(novel_id=uuid4(), consumer_feature="chapter_frontmatter") == []
        )

    async def test_frontmatter_list_value_checks_each_item(self) -> None:
        kb = FakeKBRepo()
        kb.seed(make_entry(name="Sunhaven"))
        chapter_repo = FakeChapterRepo()
        chapter_repo.seed(make_chapter(content="---\ncharacters: ['Sunhaven', 'Ghost']\n---\nBody"))
        index = make_index(kb, chapter_repo=chapter_repo)

        issues = await index.check_refs(novel_id=uuid4(), consumer_feature="chapter_frontmatter")

        # Sunhaven active -> no issue; Ghost unknown -> warned
        assert len(issues) == 1
        assert issues[0].ref_value == "Ghost"
