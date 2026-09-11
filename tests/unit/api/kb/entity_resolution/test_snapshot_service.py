"""Unit tests for the KB snapshot builder (ADR-085 P3, spec §2/§3).

The builder maps novel-scoped KB entries + relationship adjacency into
pure ``EntitySnapshot`` tuples for the resolution engine. Scope decisions
pinned here: deprecated entries excluded by the builder, series-canon
rows structurally excluded by the novel-scoped fetch, provenance parsed
tolerantly (malformed → ``None``, ranges derived from the ``chapters``
tuple — never the stored first/last pair, which out-of-order
endorsements can leave inconsistent), empty-name entries skipped (an
empty name pins S1 EXACT and could poison the engine), and neighbor ids
collected from both relationship directions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from narrare_core.kb.resolution import EntryProvenance
from narrare_core.kb.schemas.entry import NovelKBEntry

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.entity_resolution.snapshot_service import SnapshotBuilder


def _make_builder(
    kb_repo: _FakeKBRepo,
    rel_repo: _FakeRelationshipRepo,
) -> SnapshotBuilder:
    from narrare.kb.entity_resolution.snapshot_service import SnapshotBuilder

    return SnapshotBuilder(
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        relationship_repo=cast("RelationshipRepositoryProtocol", rel_repo),
    )


def _entry(
    name: str = "Anna",
    *,
    status: str = "draft",
    metadata: dict[str, object] | None = None,
    novel_id: UUID | None = None,
    entry_id: UUID | None = None,
    entity_type: str = "character",
) -> NovelKBEntry:
    return NovelKBEntry(
        id=entry_id or uuid4(),
        entity_type=entity_type,
        name=name,
        slug="slug-placeholder",
        status=status,
        metadata_=metadata,
        novel_id=novel_id or uuid4(),
    )


def _provenance(
    chapters: list[object],
    first_seen: int = 0,
    last_seen: int = 0,
    name_variants: list[object] | None = None,
) -> dict[str, object]:
    return {
        "chapters": chapters,
        "first_seen_chapter": first_seen,
        "last_seen_chapter": last_seen,
        "name_variants": name_variants if name_variants is not None else ["Anna"],
    }


class _FakeKBRepo:
    """Fake KB repo exposing only the novel-wide overlay fetch.

    Mirrors the production ``find_overlay_for_novel`` query semantics:
    returns exclusively rows with ``novel_id == X`` — series-canon rows
    (``novel_id IS NULL``) can never be returned.
    """

    def __init__(self) -> None:
        self._entries: list[NovelKBEntry] = []
        self.requested_novel_ids: list[UUID] = []

    def seed(self, entry: NovelKBEntry) -> None:
        self._entries.append(entry)

    async def find_overlay_for_novel(self, novel_id: UUID) -> list[NovelKBEntry]:
        self.requested_novel_ids.append(novel_id)
        return [e for e in self._entries if e.novel_id == novel_id]


class _FakeRelationshipRepo:
    """Fake relationship repo exposing only the novel-wide adjacency map."""

    def __init__(self, adjacency: dict[str, set[str]] | None = None) -> None:
        self._adjacency: dict[str, set[str]] = adjacency or {}
        self.requested_novel_ids: list[UUID] = []

    async def get_adjacency_map(
        self,
        novel_id: UUID,
        entity_ids: set[UUID] | None = None,
    ) -> dict[str, set[str]]:
        self.requested_novel_ids.append(novel_id)
        return dict(self._adjacency)


class TestScope:
    """Novel-scope fetching, deprecated exclusion, empty-novel behavior."""

    @pytest.mark.asyncio
    async def test_maps_entry_fields_into_snapshot(self) -> None:
        novel = uuid4()
        entry = _entry(
            name="Anna Meyer",
            status="reviewed",
            entity_type="character",
            metadata={"age": 24},
            novel_id=novel,
        )
        kb_repo = _FakeKBRepo()
        kb_repo.seed(entry)
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)

        assert len(snapshots) == 1
        snap = snapshots[0]
        assert snap.entry_id == entry.id
        assert snap.name == "Anna Meyer"
        assert snap.entity_type == "character"
        assert snap.status == "reviewed"
        assert snap.metadata == {"age": 24}
        assert snap.embedding is None  # v1: S5 stays 0 until pgvector wiring

    @pytest.mark.asyncio
    async def test_snapshot_metadata_is_a_defensive_copy(self) -> None:
        novel = uuid4()
        metadata: dict[str, object] = {"age": 24}
        kb_repo = _FakeKBRepo()
        kb_repo.seed(_entry(novel_id=novel, metadata=metadata))
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)
        metadata["age"] = 99

        assert snapshots[0].metadata == {"age": 24}

    @pytest.mark.asyncio
    async def test_excludes_deprecated_entries(self) -> None:
        novel = uuid4()
        active = _entry(name="Anna", novel_id=novel)
        deprecated = _entry(name="Anna Meyer", status="deprecated", novel_id=novel)
        kb_repo = _FakeKBRepo()
        kb_repo.seed(active)
        kb_repo.seed(deprecated)
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)

        assert [s.entry_id for s in snapshots] == [active.id]

    @pytest.mark.asyncio
    async def test_fetches_only_requested_novel_scope_canon_structurally_excluded(
        self,
    ) -> None:
        novel_a = uuid4()
        novel_b = uuid4()
        in_scope = _entry(name="Anna", novel_id=novel_a)
        kb_repo = _FakeKBRepo()
        kb_repo.seed(in_scope)
        kb_repo.seed(_entry(name="Other Novel Entity", novel_id=novel_b))
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel_a)

        assert kb_repo.requested_novel_ids == [novel_a]
        assert [s.entry_id for s in snapshots] == [in_scope.id]
        # Series-canon rows (novel_id IS NULL) are excluded by the
        # novel-scoped fetch itself — they can never leak in.

    @pytest.mark.asyncio
    async def test_empty_novel_returns_empty_tuple(self) -> None:
        builder = _make_builder(_FakeKBRepo(), _FakeRelationshipRepo())

        assert await builder.build(uuid4()) == ()


class TestProvenance:
    """Tolerant provenance parsing; ranges derived from chapters tuple."""

    @pytest.mark.asyncio
    async def test_valid_provenance_ranges_derived_from_chapters_not_stored_pair(
        self,
    ) -> None:
        # Out-of-order endorsements can leave stored first > last; the
        # builder must derive ranges from the sorted chapters tuple.
        novel = uuid4()
        metadata: dict[str, object] = {
            "provenance": _provenance(
                chapters=[3, 1, 2],
                first_seen=99,
                last_seen=0,
                name_variants=["Anna", "Anna Meyer"],
            ),
        }
        kb_repo = _FakeKBRepo()
        kb_repo.seed(_entry(novel_id=novel, metadata=metadata))
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)

        assert snapshots[0].provenance == EntryProvenance(
            chapters=(1, 2, 3),
            first_seen_chapter=1,
            last_seen_chapter=3,
            name_variants=("Anna", "Anna Meyer"),
        )

    @pytest.mark.asyncio
    async def test_missing_provenance_is_none(self) -> None:
        novel = uuid4()
        kb_repo = _FakeKBRepo()
        kb_repo.seed(_entry(name="No Metadata", novel_id=novel, metadata=None))
        kb_repo.seed(_entry(name="No Provenance Key", novel_id=novel, metadata={"age": 24}))
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)

        assert all(s.provenance is None for s in snapshots)

    @pytest.mark.asyncio
    async def test_invalid_provenance_shapes_are_none(self) -> None:
        novel = uuid4()
        invalid_blocks: list[object] = [
            "junk",
            {"chapters": "nope"},
            {"chapters": []},
            {"chapters": ["1", 2]},  # non-int member → whole block unknown
            {"chapters": [True, 2]},  # bools are not chapter positions
        ]
        kb_repo = _FakeKBRepo()
        for i, block in enumerate(invalid_blocks):
            kb_repo.seed(
                _entry(
                    name=f"Entry {i}",
                    novel_id=novel,
                    metadata={"provenance": block},
                )
            )
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)

        assert all(s.provenance is None for s in snapshots)

    @pytest.mark.asyncio
    async def test_non_string_name_variants_dropped_provenance_stays_known(self) -> None:
        # name_variants is cosmetic: corrupted members are dropped, but
        # valid chapters keep the provenance known (never negative).
        novel = uuid4()
        metadata: dict[str, object] = {
            "provenance": _provenance(
                chapters=[2],
                name_variants=["Anna", 42, None],
            ),
        }
        kb_repo = _FakeKBRepo()
        kb_repo.seed(_entry(novel_id=novel, metadata=metadata))
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)

        assert snapshots[0].provenance is not None
        assert snapshots[0].provenance.name_variants == ("Anna",)


class TestEmptyNameSkip:
    """Empty/whitespace names are skipped — they pin S1 EXACT (review finding)."""

    @pytest.mark.asyncio
    async def test_blank_name_entries_are_skipped(self) -> None:
        novel = uuid4()
        valid = _entry(name="Anna", novel_id=novel)
        kb_repo = _FakeKBRepo()
        kb_repo.seed(_entry(name="", novel_id=novel))
        kb_repo.seed(_entry(name="   ", novel_id=novel))
        kb_repo.seed(valid)
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)

        assert [s.entry_id for s in snapshots] == [valid.id]


class TestNeighbors:
    """Neighbor ids come from relationship adjacency, both directions."""

    @pytest.mark.asyncio
    async def test_neighbor_ids_collected_from_both_sides(self) -> None:
        novel = uuid4()
        anna = _entry(name="Anna", novel_id=novel)
        bruno = _entry(name="Bruno", novel_id=novel)
        clara = _entry(name="Clara", novel_id=novel)
        adjacency: dict[str, set[str]] = {
            str(anna.id): {str(bruno.id), str(clara.id)},  # outgoing + incoming
            str(bruno.id): {str(anna.id)},
        }
        kb_repo = _FakeKBRepo()
        kb_repo.seed(anna)
        kb_repo.seed(bruno)
        kb_repo.seed(clara)
        builder = _make_builder(kb_repo, _FakeRelationshipRepo(adjacency))

        snapshots = await builder.build(novel)
        by_id = {s.entry_id: s for s in snapshots}

        assert by_id[anna.id].neighbor_ids == frozenset({bruno.id, clara.id})
        assert by_id[bruno.id].neighbor_ids == frozenset({anna.id})
        # Clara has no adjacency entry → empty neighbor set, not an error.
        assert by_id[clara.id].neighbor_ids == frozenset()

    @pytest.mark.asyncio
    async def test_no_relationships_yields_empty_neighbor_sets(self) -> None:
        novel = uuid4()
        kb_repo = _FakeKBRepo()
        kb_repo.seed(_entry(name="Anna", novel_id=novel))
        builder = _make_builder(kb_repo, _FakeRelationshipRepo())

        snapshots = await builder.build(novel)

        assert snapshots[0].neighbor_ids == frozenset()
