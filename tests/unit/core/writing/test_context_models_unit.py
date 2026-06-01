"""Tests for writing/context_models.py — KBEntity, RecentChapter, ContextMetadata.

Covers:
1. KBEntity defaults and relevance_score calculation
2. RecentChapter creation
3. ContextMetadata defaults and to_dict serialization
"""

from __future__ import annotations

from uuid import uuid4

from narrare_core.writing.context_models import ContextMetadata, KBEntity, RecentChapter

# ---------------------------------------------------------------------------
# KBEntity
# ---------------------------------------------------------------------------


class TestKBEntity:
    """KBEntity dataclass with score calculations."""

    def test_defaults(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="Alice",
            content="A warrior.",
        )
        assert entity.similarity_score == 0.0
        assert entity.frequency_score == 0.0
        assert entity.recency_score == 0.0
        assert entity.is_referenced is False
        assert entity.is_pinned is False
        assert entity.metadata is None

    def test_relevance_score_calculation(self) -> None:
        """relevance_score = 50% similarity + 30% frequency + 20% recency."""
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="Alice",
            content="A warrior.",
            similarity_score=1.0,
            frequency_score=1.0,
            recency_score=1.0,
        )
        assert entity.relevance_score == 1.0

    def test_relevance_score_partial(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="Alice",
            content="A warrior.",
            similarity_score=0.8,
            frequency_score=0.5,
            recency_score=0.2,
        )
        # 0.8*0.5 + 0.5*0.3 + 0.2*0.2 = 0.4 + 0.15 + 0.04 = 0.59
        assert abs(entity.relevance_score - 0.59) < 0.001

    def test_relevance_score_all_zero(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="location",
            name="Castle",
            content="An old castle.",
        )
        assert entity.relevance_score == 0.0

    def test_with_metadata(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="Alice",
            content="A warrior.",
            metadata={"speech": {"dialect": "Southern"}},
        )
        assert entity.metadata is not None
        assert entity.metadata["speech"]["dialect"] == "Southern"


# ---------------------------------------------------------------------------
# RecentChapter
# ---------------------------------------------------------------------------


class TestRecentChapter:
    """RecentChapter dataclass."""

    def test_creation(self) -> None:
        chapter_id = uuid4()
        chapter = RecentChapter(
            chapter_id=chapter_id,
            title="Chapter 1",
            full_text="The hero enters the forest.",
            summary="Hero enters forest.",
            position=1,
        )
        assert chapter.chapter_id == chapter_id
        assert chapter.title == "Chapter 1"
        assert chapter.position == 1

    def test_all_fields_required(self) -> None:
        """All fields are required — no defaults."""
        import dataclasses

        assert len(dataclasses.fields(RecentChapter)) == 5


# ---------------------------------------------------------------------------
# ContextMetadata
# ---------------------------------------------------------------------------


class TestContextMetadata:
    """ContextMetadata dataclass with serialization."""

    def test_defaults(self) -> None:
        meta = ContextMetadata()
        assert meta.kb_characters_count == 0
        assert meta.kb_locations_count == 0
        assert meta.kb_factions_count == 0
        assert meta.kb_suggested_count == 0
        assert meta.kb_pinned_count == 0
        assert meta.recent_chapter_count == 0
        assert meta.character_names == []
        assert meta.location_names == []
        assert meta.faction_names == []
        assert meta.is_first_chapter is False
        assert meta.has_user_preferences is False
        assert meta.tone == "balanced"
        assert meta.kb_systems_count == 0
        assert meta.kb_timelines_count == 0
        assert meta.story_structure == ""
        assert meta.timeline_position == ""
        assert meta.total_budget_tokens == 0

    def test_to_dict(self) -> None:
        meta = ContextMetadata(
            kb_characters_count=3,
            character_names=["Alice", "Bob", "Eve"],
            is_first_chapter=True,
            tone="dark",
            total_budget_tokens=4000,
        )
        d = meta.to_dict()
        assert d["kb_characters_count"] == 3
        assert d["character_names"] == ["Alice", "Bob", "Eve"]
        assert d["is_first_chapter"] is True
        assert d["tone"] == "dark"
        assert d["total_budget_tokens"] == 4000

    def test_to_dict_keys_complete(self) -> None:
        """to_dict includes all expected keys."""
        meta = ContextMetadata()
        d = meta.to_dict()
        expected_keys = {
            "kb_characters_count",
            "kb_locations_count",
            "kb_factions_count",
            "kb_relationships_count",
            "kb_suggested_count",
            "kb_pinned_count",
            "recent_chapter_count",
            "character_names",
            "location_names",
            "faction_names",
            "is_first_chapter",
            "has_user_preferences",
            "tone",
            "kb_systems_count",
            "kb_timelines_count",
            "story_structure",
            "timeline_position",
            "wiki_summaries_count",
            "wiki_summaries_stale",
            "total_budget_tokens",
        }
        assert set(d.keys()) == expected_keys

    def test_custom_values_with_new_fields(self) -> None:
        """ContextMetadata with CR-04 fields."""
        meta = ContextMetadata(
            kb_systems_count=2,
            kb_timelines_count=1,
            story_structure="3-Act Structure",
            timeline_position="Day 5",
        )
        assert meta.kb_systems_count == 2
        assert meta.kb_timelines_count == 1
        assert meta.story_structure == "3-Act Structure"
        assert meta.timeline_position == "Day 5"


# ---------------------------------------------------------------------------
# CR-04: KBEntity status and updated_at
# ---------------------------------------------------------------------------


class TestKBEntityStatus:
    """KBEntity.status field (CR-04)."""

    def test_status_defaults_to_canon(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="X",
            content="X",
        )
        assert entity.status == "canon"

    def test_status_can_be_set(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="X",
            content="X",
            status="reviewed",
        )
        assert entity.status == "reviewed"

    def test_status_deprecated(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="X",
            content="X",
            status="deprecated",
        )
        assert entity.status == "deprecated"


class TestKBEntityUpdatedAt:
    """KBEntity.updated_at field (CR-04)."""

    def test_updated_at_defaults_to_none(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="X",
            content="X",
        )
        assert entity.updated_at is None

    def test_updated_at_can_be_set(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            entity_type="character",
            name="X",
            content="X",
            updated_at="2024-01-15T10:00:00Z",
        )
        assert entity.updated_at == "2024-01-15T10:00:00Z"
