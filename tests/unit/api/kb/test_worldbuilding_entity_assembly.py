"""Unit tests for worldbuilding_entity_assembly — data collection and prioritization.

Tests entity listing, summary building, token-budget prioritization,
and template/relationship-type lookup functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

from narrare.kb.worldbuilding_entity_assembly import (
    _compute_fill_rate,
    build_available_rel_types,
    build_entity_summaries,
    build_template_structures,
    get_adjacency_safe,
    get_relationships_for,
    list_entities,
    prioritize_entities,
)
from narrare_core.agents.worldbuilding_types import Phase1EntitySummary

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.models import KBEntry

# ---------------------------------------------------------------------------
# Fake classes
# ---------------------------------------------------------------------------


class FakeKBEntry:
    """Minimal stand-in for KBEntry with just the fields we need."""

    def __init__(
        self,
        *,
        id: object | None = None,
        name: str = "Test Entity",
        entity_type: str = "character",
        metadata_: dict[str, object] | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
        usage_count: int = 0,
        novel_id: object | None = None,
    ) -> None:
        self.id = id if id is not None else uuid4()
        self.name = name
        self.entity_type = entity_type
        self.metadata_ = metadata_
        self.body = body
        self.tags = tags
        self.usage_count = usage_count
        self.novel_id = novel_id if novel_id is not None else uuid4()


class FakeKBRepo:
    """In-memory fake for KBRepositoryProtocol.list_entries pagination."""

    def __init__(self, entries: list[FakeKBEntry]) -> None:
        self._entries = entries

    async def list_entries(
        self,
        novel_id: object,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[FakeKBEntry], int]:
        start = (page - 1) * page_size
        end = start + page_size
        page_items = self._entries[start:end]
        return page_items, len(self._entries)


class FakeRelEntry:
    """Minimal fake for a relationship row returned by list_for_entry."""

    def __init__(
        self,
        *,
        id: object | None = None,
        source_id: object | None = None,
        target_id: object | None = None,
        rel_type: str = "ally",
        direction: str = "directed",
    ) -> None:
        self.id = id if id is not None else uuid4()
        self.source_id = source_id if source_id is not None else uuid4()
        self.target_id = target_id if target_id is not None else uuid4()
        self.rel_type = rel_type
        self.direction = direction


class FakeRelRepo:
    """In-memory fake for RelationshipRepositoryProtocol."""

    def __init__(
        self,
        adjacency: dict[str, set[str]] | None = None,
        relationships: list[FakeRelEntry] | None = None,
    ) -> None:
        self._adjacency = adjacency or {}
        self._relationships = relationships or []
        self._raise_adjacency = False

    async def get_adjacency_map(
        self,
        novel_id: object,
        entity_ids: set[object] | None = None,
    ) -> dict[str, set[str]]:
        if self._raise_adjacency:
            raise RuntimeError("adjacency unavailable")
        return self._adjacency

    async def list_for_entry(
        self,
        entry_id: object,
        direction: str | None = None,
    ) -> list[FakeRelEntry]:
        return self._relationships


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    *,
    name: str = "Test",
    entity_type: str = "character",
    usage_count: int = 0,
    body: str | None = "Some body text",
    metadata_: dict[str, object] | None = None,
) -> FakeKBEntry:
    return FakeKBEntry(
        name=name,
        entity_type=entity_type,
        usage_count=usage_count,
        body=body,
        metadata_=metadata_,
    )


def _make_summary(
    *,
    entry_id: str | None = None,
    name: str = "Test",
    entity_type: str = "character",
    chapter_references: int = 0,
    relationship_count: int = 0,
    has_body: bool = True,
    field_fill_rate: float = 0.5,
) -> Phase1EntitySummary:
    return Phase1EntitySummary(
        entry_id=entry_id or str(uuid4()),
        name=name,
        entity_type=entity_type,
        field_fill_rate=field_fill_rate,
        relationship_count=relationship_count,
        has_body=has_body,
        chapter_references=chapter_references,
    )


# ---------------------------------------------------------------------------
# Tests: list_entities
# ---------------------------------------------------------------------------


class TestListEntities:
    """Tests for list_entities pagination and filtering."""

    async def test_list_entities_single_page_returns_all(self) -> None:
        entries = [_make_entry(name=f"E{i}") for i in range(3)]
        repo = FakeKBRepo(entries)
        result = await list_entities(cast("KBRepositoryProtocol", repo), uuid4(), None)
        assert len(result) == 3

    async def test_list_entities_multi_page_collects_all(self) -> None:
        entries = [_make_entry(name=f"E{i}") for i in range(150)]
        repo = FakeKBRepo(entries)
        result = await list_entities(cast("KBRepositoryProtocol", repo), uuid4(), None)
        assert len(result) == 150

    async def test_list_entities_with_type_filter_returns_matching(self) -> None:
        entries = [
            _make_entry(entity_type="character", name="Alice"),
            _make_entry(entity_type="location", name="Castle"),
            _make_entry(entity_type="character", name="Bob"),
        ]
        repo = FakeKBRepo(entries)
        result = await list_entities(cast("KBRepositoryProtocol", repo), uuid4(), ["character"])
        assert len(result) == 2
        assert all(e.entity_type == "character" for e in result)

    async def test_list_entities_without_filter_returns_all(self) -> None:
        entries = [_make_entry(entity_type="character"), _make_entry(entity_type="location")]
        repo = FakeKBRepo(entries)
        result = await list_entities(cast("KBRepositoryProtocol", repo), uuid4(), None)
        assert len(result) == 2


class TestGetAdjacencySafe:
    async def test_get_adjacency_safe_success_returns_map(self) -> None:
        entity = _make_entry()
        adj = {"x": {"y"}}
        repo = FakeRelRepo(adjacency=adj)
        result = await get_adjacency_safe(
            cast("RelationshipRepositoryProtocol", repo), uuid4(), cast("list[KBEntry]", [entity])
        )
        assert result == adj

    async def test_get_adjacency_safe_exception_returns_empty(self) -> None:
        entity = _make_entry()
        repo = FakeRelRepo()
        repo._raise_adjacency = True
        result = await get_adjacency_safe(
            cast("RelationshipRepositoryProtocol", repo), uuid4(), cast("list[KBEntry]", [entity])
        )
        assert result == {}


class TestBuildEntitySummaries:
    """Tests for build_entity_summaries construction."""

    def test_build_entity_summaries_correct_fields(self) -> None:
        entry = _make_entry(name="Alice", entity_type="character", usage_count=5)
        summaries = build_entity_summaries(cast("list[KBEntry]", [entry]), {})
        assert len(summaries) == 1
        assert summaries[0].name == "Alice"
        assert summaries[0].chapter_references == 5

    def test_build_entity_summaries_zero_relationships(self) -> None:
        summaries = build_entity_summaries(cast("list[KBEntry]", [_make_entry()]), {})
        assert summaries[0].relationship_count == 0

    def test_build_entity_summaries_empty_metadata_defaults(self) -> None:
        entry = _make_entry(metadata_=None, body="text")
        summaries = build_entity_summaries(cast("list[KBEntry]", [entry]), {})
        assert summaries[0].field_fill_rate == 0.0


class TestPrioritizeEntities:
    """Tests for 4-tier entity prioritization within token budget."""

    def test_prioritize_tier1_chapter_referenced(self) -> None:
        s1 = _make_summary(chapter_references=3)
        s2 = _make_summary(chapter_references=0)
        result = prioritize_entities([s1, s2], budget=8000)
        assert s1.entry_id in [s.entry_id for s in result]

    def test_prioritize_tier2_well_connected(self) -> None:
        s1 = _make_summary(relationship_count=5, chapter_references=0)
        s2 = _make_summary(relationship_count=1, chapter_references=0)
        result = prioritize_entities([s1, s2], budget=8000)
        assert s1.entry_id in [s.entry_id for s in result]

    def test_prioritize_tier3_remaining(self) -> None:
        s1 = _make_summary(chapter_references=0, relationship_count=0)
        s2 = _make_summary(chapter_references=0, relationship_count=0)
        result = prioritize_entities([s1, s2], budget=500)
        assert len(result) >= 1

    def test_prioritize_budget_exceeded_drops_low_priority(self) -> None:
        low = _make_summary(chapter_references=0, relationship_count=0)
        high = _make_summary(chapter_references=10)
        result = prioritize_entities([low, high], budget=500)
        assert high.entry_id in [s.entry_id for s in result]
        assert low.entry_id not in [s.entry_id for s in result]


class TestGetRelationshipsFor:
    async def test_get_relationships_deduplicates(self) -> None:
        rel = FakeRelEntry()
        repo = FakeRelRepo(relationships=[rel])
        s1 = _make_summary(entry_id=str(uuid4()))
        s2 = _make_summary(entry_id=str(uuid4()))
        result = await get_relationships_for([s1, s2], cast("RelationshipRepositoryProtocol", repo))
        assert len(result) == 1

    async def test_get_relationships_empty_returns_empty(self) -> None:
        repo = FakeRelRepo(relationships=[])
        result = await get_relationships_for(
            [_make_summary()], cast("RelationshipRepositoryProtocol", repo)
        )
        assert result == []


class TestBuildTemplateStructures:
    def test_build_template_structures_character(self) -> None:
        result = build_template_structures({"character"})
        assert "character" in result
        assert len(result["character"]) > 0

    def test_build_template_structures_multiple_types(self) -> None:
        result = build_template_structures({"character", "location"})
        assert "character" in result
        assert "location" in result


class TestBuildAvailableRelTypes:
    def test_build_available_rel_types_generates_pairs(self) -> None:
        result = build_available_rel_types({"character", "location"})
        assert "character->character" in result
        assert "character->location" in result

    def test_build_available_rel_types_unknown_pair_empty(self) -> None:
        result = build_available_rel_types({"concept"})
        assert "concept->concept" not in result


class TestComputeFillRate:
    def test_compute_fill_rate_all_filled(self) -> None:
        assert _compute_fill_rate({"name": "Alice", "role": "hero"}, ["name", "role"]) == 1.0

    def test_compute_fill_rate_none_filled(self) -> None:
        assert _compute_fill_rate({"name": None, "role": None}, ["name", "role"]) == 0.0

    def test_compute_fill_rate_empty_field_keys_returns_one(self) -> None:
        assert _compute_fill_rate({}, []) == 1.0

    def test_compute_fill_rate_partial(self) -> None:
        assert _compute_fill_rate({"a": "filled", "b": None}, ["a", "b"]) == 0.5

    def test_compute_fill_rate_empty_string_not_filled(self) -> None:
        assert _compute_fill_rate({"name": ""}, ["name"]) == 0.0
