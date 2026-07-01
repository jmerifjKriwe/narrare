"""Unit tests for the pure helpers in ``ref_index_helpers`` (ADR-050 P1-B).

These helpers flatten consumer-side KB refs into scalar strings and build typed
``RefIntegrityIssue`` objects. They are pure functions with no I/O, so each
branch is exercised directly.
"""

from __future__ import annotations

from uuid import uuid4

from narrare.chapters.models import Chapter
from narrare.consistency.ref_index_helpers import (
    build_ref_issue,
    chapter_ref_values,
    iter_scalar_refs,
    parse_uuid,
    storyboard_texts,
)
from narrare.planning.models import ChapterOutline
from narrare_core.context.integration_contracts import RefIntegrityIssue


def _chapter(*, content: str = "", pov_character_id: str = "") -> Chapter:
    return Chapter(
        id=uuid4(),
        novel_id=uuid4(),
        content=content,
        pov_character_id=pov_character_id,
    )


def _outline(
    *,
    planned_beats: list[dict[str, object]] | None = None,
    outline_notes: str = "",
) -> ChapterOutline:
    return ChapterOutline(
        id=uuid4(),
        chapter_id=uuid4(),
        planned_beats=list(planned_beats or []),
        outline_notes=outline_notes,
    )


class TestChapterRefValues:
    def test_extracts_known_frontmatter_ref_keys(self) -> None:
        entity = uuid4()
        chapter = _chapter(
            content=(
                f"---\ncharacters: ['{entity}']\n"
                f"location: '{entity}'\nfactions: ['guild']\n---\nBody"
            ),
        )
        locations = {loc for loc, _ in chapter_ref_values(chapter)}

        assert f"chapters[{chapter.id}].frontmatter.characters" in locations
        assert f"chapters[{chapter.id}].frontmatter.location" in locations
        assert f"chapters[{chapter.id}].frontmatter.factions" in locations

    def test_ignores_non_ref_frontmatter_keys(self) -> None:
        chapter = _chapter(content="---\ntitle: Hello\nsummary: text\n---\nBody")
        assert chapter_ref_values(chapter) == []

    def test_includes_pov_character_id_when_present(self) -> None:
        chapter = _chapter(pov_character_id="char-123")
        refs = chapter_ref_values(chapter)
        assert any(
            loc == f"chapters[{chapter.id}].pov_character_id" and value == "char-123"
            for loc, value in refs
        )

    def test_skips_empty_pov_character_id(self) -> None:
        chapter = _chapter(content="---\ntitle: x\n---\n", pov_character_id="")
        assert chapter_ref_values(chapter) == []

    def test_no_frontmatter_returns_empty(self) -> None:
        chapter = _chapter(content="Just plain body text, no frontmatter.")
        assert chapter_ref_values(chapter) == []


class TestStoryboardTexts:
    def test_collects_beat_text_and_outline_notes(self) -> None:
        outline = _outline(
            planned_beats=[{"text": "Alice meets the dragon"}, {"text": "Bob flees"}],
            outline_notes="Notes about the guild",
        )
        texts = storyboard_texts(outline)
        locations = [loc for loc, _ in texts]

        assert any(".planned_beats[0].text" in loc for loc in locations)
        assert any(".planned_beats[1].text" in loc for loc in locations)
        assert any(".outline_notes" in loc for loc in locations)
        assert len(texts) == 3

    def test_skips_non_string_beat_text(self) -> None:
        outline = _outline(planned_beats=[{"text": 123}, {"text": None}])
        assert storyboard_texts(outline) == []

    def test_skips_non_dict_beats(self) -> None:
        outline = _outline(planned_beats=["not-a-dict", 42, None])  # type: ignore[list-item]
        assert storyboard_texts(outline) == []

    def test_empty_beats_and_notes_returns_empty(self) -> None:
        assert storyboard_texts(_outline()) == []
        assert storyboard_texts(_outline(planned_beats=[])) == []


class TestParseUuid:
    def test_valid_uuid_string_round_trips(self) -> None:
        value = uuid4()
        assert parse_uuid(str(value)) == value

    def test_non_uuid_legacy_ref_returns_none(self) -> None:
        assert parse_uuid("not-a-uuid") is None
        assert parse_uuid("alice") is None
        assert parse_uuid("") is None


class TestIterScalarRefs:
    def test_string_returns_singleton_list(self) -> None:
        assert iter_scalar_refs("alice") == ["alice"]

    def test_list_filters_non_string_items(self) -> None:
        assert iter_scalar_refs(["a", 3, "b", None, True]) == ["a", "b"]

    def test_dict_extracts_id_and_name_fields(self) -> None:
        assert iter_scalar_refs({"id": "x", "name": "y"}) == ["x", "y"]

    def test_dict_skips_non_string_id_and_name(self) -> None:
        assert iter_scalar_refs({"id": 5, "name": None}) == []

    def test_other_types_return_empty(self) -> None:
        assert iter_scalar_refs(42) == []
        assert iter_scalar_refs(None) == []
        assert iter_scalar_refs(3.14) == []
        assert iter_scalar_refs(True) == []


class TestBuildRefIssue:
    def test_constructs_typed_issue_with_all_fields(self) -> None:
        issue = build_ref_issue(
            consumer_feature="timeline",
            location="timeline_events[1].character_refs[0]",
            ref_kind="id",
            ref_value="abc-123",
            resolved_status="deprecated",
            reason="deprecated_ref_in_active_context",
            suggested_action="mark_deprecated_in_context",
        )

        assert isinstance(issue, RefIntegrityIssue)
        assert issue.consumer_feature == "timeline"
        assert issue.consumer_location == "timeline_events[1].character_refs[0]"
        assert issue.ref_kind == "id"
        assert issue.ref_value == "abc-123"
        assert issue.resolved_status == "deprecated"
        assert issue.reason == "deprecated_ref_in_active_context"
        assert issue.suggested_action == "mark_deprecated_in_context"
