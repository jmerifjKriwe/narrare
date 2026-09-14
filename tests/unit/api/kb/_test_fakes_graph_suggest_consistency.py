"""Shared fakes for the KB graph + suggest + consistency ownership matrix (S9).

Recording/counting fakes for ``GraphService``, ``KBSuggestService``, and
``KBConsistencyService`` dependencies, plus service factories over a
``FakeNovelRepo`` ownership map. Split from ``_test_fakes.py`` for
RULE-04 compliance (file-size hard limit) — same pattern as
``_test_fakes_improve_worldbuilding.py`` (S8).

Every fake records the calls that must NOT happen for a foreign caller:
data reads (entries/relationships/adjacency/chapter), cache probes, and
LLM boundaries (proactive suggest, consistency analyzers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare_core.context.suggestion import EntityMetadata, Suggestion

from ._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from datetime import datetime

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
    from narrare.kb.consistency_cache import ConsistencyCache
    from narrare.kb.consistency_service import KBConsistencyService
    from narrare.kb.contracts import (
        KBRepositoryProtocol,
        RelationshipRepositoryProtocol,
    )
    from narrare.kb.graph_service import GraphService
    from narrare.kb.relationship_asymmetry import RelationshipAsymmetryChecker
    from narrare.kb.suggest_service import KBSuggestService
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.context.contracts import ProactiveContextProtocol


# ---------------------------------------------------------------------------
# Graph fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeGraphEntry:
    """Minimal stand-in for a KBEntry row (graph + suggest fields)."""

    id: UUID = field(default_factory=uuid4)
    novel_id: UUID | None = None
    name: str = "Aria"
    entity_type: str = "character"
    status: str = "draft"
    tags: list[str] | None = None
    metadata_: dict[str, object] | None = None
    usage_count: int | None = 0
    last_referenced_at: datetime | None = None


@dataclass
class FakeGraphRelationship:
    """Minimal stand-in for a KBRelationship row."""

    id: UUID = field(default_factory=uuid4)
    source_id: UUID | None = None
    target_id: UUID | None = None
    rel_type: str = "ally"
    label: str | None = None
    direction: str = "directed"


class RecordingGraphKBRepo:
    """In-memory fake KBRepository for the graph service — records reads."""

    def __init__(self, entries: list[FakeGraphEntry] | None = None) -> None:
        self._entries = entries or []
        self.list_entries_calls: list[UUID] = []
        self.get_by_id_calls: list[UUID] = []

    async def list_entries(
        self,
        novel_id: UUID,
        page: int = 1,
        page_size: int = 50,
        **_kwargs: object,
    ) -> tuple[list[FakeGraphEntry], int]:
        self.list_entries_calls.append(novel_id)
        return self._entries, len(self._entries)

    async def get_by_id(self, entry_id: UUID) -> FakeGraphEntry | None:
        self.get_by_id_calls.append(entry_id)
        return next((e for e in self._entries if e.id == entry_id), None)


class RecordingGraphRelRepo:
    """In-memory fake RelationshipRepository — records reads."""

    def __init__(
        self,
        relationships: list[FakeGraphRelationship] | None = None,
        adjacency: dict[str, set[str]] | None = None,
    ) -> None:
        self._relationships = relationships or []
        self._adjacency = adjacency or {}
        self.list_all_calls: list[UUID] = []
        self.adjacency_calls: list[UUID] = []

    async def list_all_for_novel(self, novel_id: UUID) -> list[FakeGraphRelationship]:
        self.list_all_calls.append(novel_id)
        return self._relationships

    async def get_adjacency_map(self, novel_id: UUID) -> dict[str, set[str]]:
        self.adjacency_calls.append(novel_id)
        return self._adjacency


def make_graph_ownership_service(
    ownership: dict[UUID, UUID],
    entries: list[FakeGraphEntry] | None = None,
    relationships: list[FakeGraphRelationship] | None = None,
    adjacency: dict[str, set[str]] | None = None,
) -> tuple[
    GraphService,
    RecordingGraphKBRepo,
    RecordingGraphRelRepo,
    FakeNovelRepo,
]:
    """Build a GraphService over recording fakes + a novel ownership map."""
    from narrare.kb.graph_service import GraphService

    novel_repo = FakeNovelRepo(ownership)
    kb_repo = RecordingGraphKBRepo(entries)
    rel_repo = RecordingGraphRelRepo(relationships, adjacency)
    service = GraphService(
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        rel_repo=cast("RelationshipRepositoryProtocol", rel_repo),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
    )
    return service, kb_repo, rel_repo, novel_repo


# ---------------------------------------------------------------------------
# Suggest fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeSuggestChapter:
    """Minimal chapter-like object (content is all the service reads)."""

    content: str = "Aria entered the room."


class RecordingChapterRepo:
    """Fake ChapterRepositoryProtocol — records chapter loads."""

    def __init__(self, chapter: FakeSuggestChapter | None) -> None:
        self._chapter = chapter
        self.get_by_id_calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, chapter_id: UUID, novel_id: UUID) -> FakeSuggestChapter | None:
        self.get_by_id_calls.append((chapter_id, novel_id))
        return self._chapter


class RecordingSuggestKBRepo:
    """Fake KBRepositoryProtocol for the suggest service — records reads."""

    def __init__(self, entries: list[FakeGraphEntry] | None = None) -> None:
        self._entries = entries or []
        self.list_entries_calls: list[UUID] = []

    async def list_entries(
        self,
        novel_id: UUID,
        page: int = 1,
        page_size: int = 50,
        **_kwargs: object,
    ) -> tuple[list[FakeGraphEntry], int]:
        self.list_entries_calls.append(novel_id)
        return self._entries, len(self._entries)


class CountingProactiveContext:
    """Fake ProactiveContextProtocol — counts suggest calls (LLM boundary)."""

    def __init__(self) -> None:
        self.suggest_calls: list[UUID] = []

    async def suggest(
        self,
        chapter_content: str,
        *,
        novel_id: UUID,
        chapter_frontmatter: dict[str, object] | None = None,
        entity_names: list[str] | None = None,
        max_results: int = 20,
        entity_metadata: dict[UUID, EntityMetadata] | None = None,
    ) -> list[Suggestion]:
        self.suggest_calls.append(novel_id)
        return [
            Suggestion(
                entry_id=uuid4(),
                entry_type="character",
                name="Aria",
                relevance_score=0.9,
                reason="mentioned_in_text",
                similarity=0.8,
                usage_count=1,
                last_referenced_at=None,
            )
        ]


def make_suggest_ownership_service(
    ownership: dict[UUID, UUID],
    chapter: FakeSuggestChapter | None,
    entries: list[FakeGraphEntry] | None = None,
) -> tuple[
    KBSuggestService,
    RecordingChapterRepo,
    RecordingSuggestKBRepo,
    CountingProactiveContext,
    FakeNovelRepo,
]:
    """Build a KBSuggestService over recording fakes + an ownership map."""
    from narrare.kb.suggest_service import KBSuggestService

    novel_repo = FakeNovelRepo(ownership)
    chapter_repo = RecordingChapterRepo(chapter)
    kb_repo = RecordingSuggestKBRepo(entries)
    proactive = CountingProactiveContext()
    service = KBSuggestService(
        proactive_context=cast("ProactiveContextProtocol", proactive),
        chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
    )
    return service, chapter_repo, kb_repo, proactive, novel_repo


# ---------------------------------------------------------------------------
# Consistency fakes
# ---------------------------------------------------------------------------


class CountingConsistencyAnalyzer:
    """Fake KBConsistencyAnalyzer — counts entry-internal analysis (LLM)."""

    def __init__(self) -> None:
        self.analyze_calls: list[UUID] = []

    async def ensure_resolved(self) -> None:
        """ADR-086 L15: the service ensure-resolves before the cache probe.

        No-op here — the ownership matrix never configures a cascade.
        """

    async def analyze_entries(
        self,
        novel_id: UUID,
        entity_types: list[str] | None,
    ) -> tuple[list[object], int]:
        self.analyze_calls.append(novel_id)
        return [], 0


class StubWorldbuildingAnalyzer:
    """Resolution-only worldbuilding stub for the ownership matrix.

    The service ensure-resolves BOTH cascades after the ownership gate
    (ADR-086 L15); the ownership tests drive ``include_cross_entity=``
    False paths, so Phase 3 itself never runs and only this seam exists.
    """

    async def ensure_resolved(self) -> None:
        return None


class CountingAsymmetryChecker:
    """Fake RelationshipAsymmetryChecker — counts algorithmic phase runs."""

    def __init__(self) -> None:
        self.check_calls: list[UUID] = []

    async def check(self, novel_id: UUID) -> list[object]:
        self.check_calls.append(novel_id)
        return []


class RecordingConsistencyCache:
    """Fake ConsistencyCache — records probes and writes."""

    def __init__(self) -> None:
        self.hash_calls: int = 0
        self.get_calls: list[str] = []
        self.set_calls: list[str] = []

    def hash_entity_types(self, entity_types: list[str] | None) -> str:
        self.hash_calls += 1
        return ",".join(entity_types) if entity_types else ""

    async def get(self, novel_id: str, types_hash: str) -> str | None:
        self.get_calls.append(novel_id)
        return None

    async def set(self, novel_id: str, payload: str, types_hash: str) -> None:
        self.set_calls.append(novel_id)


def make_consistency_ownership_service(
    ownership: dict[UUID, UUID],
) -> tuple[
    KBConsistencyService,
    CountingConsistencyAnalyzer,
    CountingAsymmetryChecker,
    RecordingConsistencyCache,
    FakeNovelRepo,
]:
    """Build a KBConsistencyService over recording fakes + an ownership map.

    The worldbuilding analyzer is a never-called stub: the ownership
    tests drive the owner path with ``include_cross_entity=False`` and
    assert the foreign path never reaches ANY phase.
    """
    from narrare.kb.consistency_service import KBConsistencyService

    novel_repo = FakeNovelRepo(ownership)
    analyzer = CountingConsistencyAnalyzer()
    asymmetry_checker = CountingAsymmetryChecker()
    cache = RecordingConsistencyCache()
    service = KBConsistencyService(
        analyzer=cast("KBConsistencyAnalyzer", analyzer),
        asymmetry_checker=cast("RelationshipAsymmetryChecker", asymmetry_checker),
        worldbuilding_analyzer=cast("WorldbuildingAnalyzer", StubWorldbuildingAnalyzer()),
        kb_repo=cast("KBRepositoryProtocol", object()),
        rel_repo=cast("RelationshipRepositoryProtocol", object()),
        cache=cast("ConsistencyCache", cache),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
    )
    return service, analyzer, asymmetry_checker, cache, novel_repo


__all__ = [
    "CountingAsymmetryChecker",
    "CountingConsistencyAnalyzer",
    "CountingProactiveContext",
    "FakeGraphEntry",
    "FakeGraphRelationship",
    "FakeSuggestChapter",
    "RecordingChapterRepo",
    "RecordingConsistencyCache",
    "RecordingGraphKBRepo",
    "RecordingGraphRelRepo",
    "RecordingSuggestKBRepo",
    "StubWorldbuildingAnalyzer",
    "make_consistency_ownership_service",
    "make_graph_ownership_service",
    "make_suggest_ownership_service",
]
