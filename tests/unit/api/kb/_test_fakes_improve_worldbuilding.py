"""Shared fakes for the KB improve + worldbuilding ownership matrix (S8).

Recording/counting fakes for KBImproveService and WorldbuildingService
dependencies, plus canned analysis builders and service factories over a
``FakeNovelRepo`` ownership map. Split from ``_test_fakes.py`` for
RULE-04 compliance (file-size hard limit).

The session-service fakes live in ``_test_fakes.py`` (S7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare.kb.improve_contracts import (
    ImproveSuggestionResponse,
    KBImproveAnalysisResponse,
)
from narrare.kb.worldbuilding_contracts import (
    ConnectionSuggestion,
    WorldbuildingAnalysisResponse,
)

from ._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare.kb.improve_service import KBImproveService
    from narrare.kb.models import KBRelationship
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare.kb.worldbuilding_service import WorldbuildingService
    from narrare.novels.contracts import NovelRepositoryProtocol


@dataclass
class FakeKBEntry:
    """Minimal stand-in for a KBEntry row — carries the ownership-relevant fields."""

    id: UUID
    novel_id: UUID
    name: str = "Aria"
    entity_type: str = "character"
    metadata_: dict[str, object] | None = None
    body: str = ""
    tags: list[str] | None = None


class RecordingKBRepo:
    """In-memory fake KBRepository — records reads and entry updates.

    ``own_all_entries=True`` keeps the batch entry∈novel probe permissive
    (every referenced id counts as in-novel) so non-entry tests stay green;
    the default strict mode answers from the seeded entry map.
    """

    def __init__(
        self,
        entries: dict[UUID, FakeKBEntry] | None = None,
        *,
        own_all_entries: bool = False,
    ) -> None:
        self._entries = dict(entries or {})
        self._own_all = own_all_entries
        self.get_by_id_calls: list[UUID] = []
        self.update_calls: list[tuple[UUID, dict[str, object]]] = []
        self.filter_ids_in_novel_calls: list[tuple[UUID, frozenset[UUID]]] = []

    async def get_by_id(self, entry_id: UUID) -> FakeKBEntry | None:
        self.get_by_id_calls.append(entry_id)
        return self._entries.get(entry_id)

    async def update(self, entry: FakeKBEntry, data: dict[str, object]) -> FakeKBEntry:
        self.update_calls.append((entry.id, dict(data)))
        return entry

    async def filter_ids_in_novel(self, novel_id: UUID, entry_ids: set[UUID]) -> set[UUID]:
        """Batch entry∈novel ownership probe (W2) — records every call."""
        self.filter_ids_in_novel_calls.append((novel_id, frozenset(entry_ids)))
        if self._own_all:
            return set(entry_ids)
        return {
            entry_id
            for entry_id in entry_ids
            if (entry := self._entries.get(entry_id)) is not None and entry.novel_id == novel_id
        }


class RecordingRelationshipRepo:
    """In-memory fake relationship repository — records exists checks and creates."""

    def __init__(self) -> None:
        self.created: list[KBRelationship] = []
        self.exists_calls: list[tuple[UUID, UUID, str]] = []

    async def exists(self, source_id: UUID, target_id: UUID, rel_type: str) -> bool:
        self.exists_calls.append((source_id, target_id, rel_type))
        return False

    async def create(self, rel: KBRelationship) -> KBRelationship:
        self.created.append(rel)
        return rel


class CountingImproveAnalyzer:
    """Fake KBImproveAnalyzer — counts every analyzer touch (LLM boundary).

    ``get_cached_analysis`` returns the canned analysis (cache hit) so the
    apply path can be exercised without an LLM call.
    """

    def __init__(self, analysis: KBImproveAnalysisResponse | None = None) -> None:
        self._analysis = analysis or make_improve_analysis()
        self.analyze_calls: list[tuple[UUID, UUID]] = []
        self.cached_calls: list[UUID] = []
        self.invalidate_calls: list[UUID] = []

    async def analyze(self, *, novel_id: UUID, entry_id: UUID) -> KBImproveAnalysisResponse:
        self.analyze_calls.append((novel_id, entry_id))
        return self._analysis

    async def get_cached_analysis(self, entry_id: UUID) -> KBImproveAnalysisResponse:
        self.cached_calls.append(entry_id)
        return self._analysis

    async def invalidate_cache(self, entry_id: UUID) -> None:
        self.invalidate_calls.append(entry_id)


class CountingWorldbuildingAnalyzer:
    """Fake WorldbuildingAnalyzer — counts analyze invocations (LLM boundary)."""

    def __init__(self) -> None:
        self.analyze_calls: list[UUID] = []

    async def analyze(self, novel_id: UUID, request: object) -> WorldbuildingAnalysisResponse:
        self.analyze_calls.append(novel_id)
        return make_worldbuilding_analysis(novel_id)


class RecordingWorldbuildingCache:
    """Fake WorldbuildingCache — records cache invalidations."""

    def __init__(self) -> None:
        self.delete_all_calls: list[str] = []

    async def delete_all(self, novel_id: str) -> None:
        self.delete_all_calls.append(novel_id)


def make_improve_analysis() -> KBImproveAnalysisResponse:
    """A canned improve analysis with one add_field and one connect suggestion."""
    return KBImproveAnalysisResponse(
        suggestions=[
            ImproveSuggestionResponse(
                type="add_field",
                target="personality",
                description="Add personality trait",
                proposed_content="Brave and cunning",
                confidence=0.85,
                suggestion_id=0,
            ),
            ImproveSuggestionResponse(
                type="connect",
                target="mentor",
                description="Connect to mentor figure",
                related_entity_id=str(uuid4()),
                related_entity_name="Gandalf",
                confidence=0.75,
                suggestion_id=1,
            ),
        ],
        overall_assessment="Entry needs more detail",
        completeness_score=0.4,
    )


def make_worldbuilding_analysis(
    novel_id: UUID,
    suggestions: list[ConnectionSuggestion] | None = None,
) -> WorldbuildingAnalysisResponse:
    """A canned worldbuilding analysis with one connection suggestion.

    Pass explicit ``suggestions`` to control the entity ids (W2 matrix).
    """
    return WorldbuildingAnalysisResponse(
        novel_id=str(novel_id),
        entity_count=2,
        gap_findings=[],
        connection_suggestions=suggestions
        if suggestions is not None
        else [
            ConnectionSuggestion(
                finding_index=0,
                source_entity_id=str(uuid4()),
                source_entity_name="Alice",
                source_entity_type="character",
                target_entity_id=str(uuid4()),
                target_entity_name="Bob",
                target_entity_type="character",
                suggested_rel_type="ally",
                reasoning="Characters interact frequently",
                confidence=0.85,
                story_relevance=0.7,
            )
        ],
        consistency_issues=[],
        worldbuilding_score=0.75,
        overall_assessment="Good worldbuilding foundation",
        summary={
            "total_entities": 2,
            "gaps_found": 0,
            "connections_suggested": 1,
            "consistency_issues": 0,
            "entities_in_analysis": 2,
        },
        analyzed_at="2026-01-01T00:00:00Z",
    )


def make_improve_ownership_service(
    ownership: dict[UUID, UUID],
    entries: dict[UUID, FakeKBEntry],
) -> tuple[
    KBImproveService,
    CountingImproveAnalyzer,
    RecordingKBRepo,
    RecordingRelationshipRepo,
    FakeNovelRepo,
]:
    """Build a KBImproveService over recording fakes + a novel ownership map."""
    from narrare.kb.improve_service import KBImproveService

    novel_repo = FakeNovelRepo(ownership)
    kb_repo = RecordingKBRepo(entries)
    rel_repo = RecordingRelationshipRepo()
    analyzer = CountingImproveAnalyzer()
    service = KBImproveService(
        analyzer=cast("KBImproveAnalyzer", analyzer),
        kb_repo=cast("KBRepository", kb_repo),
        kb_service=cast("KBService", object()),
        rel_repo=cast("RelationshipRepository", rel_repo),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
    )
    return service, analyzer, kb_repo, rel_repo, novel_repo


def make_worldbuilding_ownership_service(
    ownership: dict[UUID, UUID],
    entries: dict[UUID, FakeKBEntry] | None = None,
) -> tuple[
    WorldbuildingService,
    CountingWorldbuildingAnalyzer,
    RecordingRelationshipRepo,
    RecordingWorldbuildingCache,
    RecordingKBRepo,
    FakeNovelRepo,
]:
    """Build a WorldbuildingService over recording fakes + a novel ownership map.

    ``entries=None`` keeps the entry repo permissive for the batch
    entry∈novel probe (every referenced id counts as in-novel); pass an
    explicit map to model the W2 entry∈novel matrix.
    """
    from narrare.kb.worldbuilding_service import WorldbuildingService

    novel_repo = FakeNovelRepo(ownership)
    rel_repo = RecordingRelationshipRepo()
    kb_repo = RecordingKBRepo(entries, own_all_entries=entries is None)
    analyzer = CountingWorldbuildingAnalyzer()
    cache = RecordingWorldbuildingCache()
    service = WorldbuildingService(
        analyzer=cast("WorldbuildingAnalyzer", analyzer),
        rel_repo=cast("RelationshipRepositoryProtocol", rel_repo),
        entry_repo=cast("KBRepositoryProtocol", kb_repo),
        cache=cast("WorldbuildingCache", cache),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
    )
    return service, analyzer, rel_repo, cache, kb_repo, novel_repo
