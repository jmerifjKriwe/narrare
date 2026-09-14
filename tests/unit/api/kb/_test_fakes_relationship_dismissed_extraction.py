"""Shared fakes for the KB relationships + dismissed + extraction ownership matrix (S10).

Recording/counting fakes for ``RelationshipService``,
``DismissedFindingService``, and ``ExtractionService`` dependencies, plus
service factories over a ``FakeNovelRepo`` ownership map — same pattern as
``_test_fakes_graph_suggest_consistency.py`` (S9).

Every fake records the calls that must NOT happen for a foreign caller:
entry/relationship reads and writes, dismissal state changes, chapter
content loads, and the LLM boundary (model resolution + agent run).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare_core.prompts.composer import ComposedPrompt

from ._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.consistency_contracts import DismissedFindingRepositoryProtocol
    from narrare.kb.contracts import (
        KBRepositoryProtocol,
        RelationshipRepositoryProtocol,
    )
    from narrare.kb.dismissed_service import DismissedFindingService
    from narrare.kb.extraction_service import ExtractionService
    from narrare.kb.relationship_service import RelationshipService
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer


# ---------------------------------------------------------------------------
# Relationship fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeRelEntry:
    """Minimal stand-in for a KBEntry row (id + novel linkage)."""

    id: UUID = field(default_factory=uuid4)
    novel_id: UUID | None = None
    name: str = "Aria"


@dataclass
class FakeRelRow:
    """Minimal stand-in for a KBRelationship row."""

    id: UUID = field(default_factory=uuid4)
    source_id: UUID = field(default_factory=uuid4)
    target_id: UUID = field(default_factory=uuid4)
    rel_type: str = "ally"


class RecordingRelEntryRepo:
    """In-memory fake KBRepository (entry lookups) — records reads."""

    def __init__(self, entries: list[FakeRelEntry] | None = None) -> None:
        self._entries = entries or []
        self.get_by_id_calls: list[UUID] = []

    async def get_by_id(self, entry_id: UUID) -> FakeRelEntry | None:
        self.get_by_id_calls.append(entry_id)
        return next((e for e in self._entries if e.id == entry_id), None)


class RecordingRelRepo:
    """In-memory fake RelationshipRepository — records reads AND writes."""

    def __init__(self, relationships: list[FakeRelRow] | None = None) -> None:
        self._relationships = {r.id: r for r in (relationships or [])}
        self.create_calls: list[FakeRelRow] = []
        self.get_by_id_calls: list[UUID] = []
        self.delete_calls: list[FakeRelRow] = []
        self.exists_calls: list[tuple[UUID, UUID, str]] = []
        self.list_for_entry_calls: list[tuple[UUID, str | None]] = []

    async def create(self, rel: FakeRelRow) -> FakeRelRow:
        self.create_calls.append(rel)
        self._relationships[rel.id] = rel
        return rel

    async def get_by_id(self, rel_id: UUID) -> FakeRelRow | None:
        self.get_by_id_calls.append(rel_id)
        return self._relationships.get(rel_id)

    async def delete(self, rel: FakeRelRow) -> None:
        self.delete_calls.append(rel)
        self._relationships.pop(rel.id, None)

    async def exists(self, source_id: UUID, target_id: UUID, rel_type: str) -> bool:
        self.exists_calls.append((source_id, target_id, rel_type))
        return any(
            r.source_id == source_id and r.target_id == target_id and r.rel_type == rel_type
            for r in self._relationships.values()
        )

    async def list_for_entry(
        self,
        entry_id: UUID,
        direction: str | None = None,
    ) -> list[FakeRelRow]:
        self.list_for_entry_calls.append((entry_id, direction))
        return [
            r
            for r in self._relationships.values()
            if r.source_id == entry_id or r.target_id == entry_id
        ]


def make_relationship_ownership_service(
    ownership: dict[UUID, UUID],
    entries: list[FakeRelEntry] | None = None,
    relationships: list[FakeRelRow] | None = None,
) -> tuple[
    RelationshipService,
    RecordingRelEntryRepo,
    RecordingRelRepo,
    FakeNovelRepo,
]:
    """Build a RelationshipService over recording fakes + an ownership map."""
    from narrare.kb.relationship_service import RelationshipService

    novel_repo = FakeNovelRepo(ownership)
    entry_repo = RecordingRelEntryRepo(entries)
    rel_repo = RecordingRelRepo(relationships)
    service = RelationshipService(
        rel_repo=cast("RelationshipRepositoryProtocol", rel_repo),
        entry_repo=cast("KBRepositoryProtocol", entry_repo),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
    )
    return service, entry_repo, rel_repo, novel_repo


# ---------------------------------------------------------------------------
# Dismissed fakes
# ---------------------------------------------------------------------------


class RecordingDismissedRepo:
    """In-memory fake DismissedFindingRepository — records state changes."""

    def __init__(
        self,
        novel_id: UUID | None = None,
        fingerprints: list[str] | None = None,
    ) -> None:
        seed_novel = novel_id if novel_id is not None else uuid4()
        self._store: dict[tuple[UUID, str], str | None] = {
            (seed_novel, fp): None for fp in (fingerprints or [])
        }
        self.dismiss_calls: list[tuple[UUID, str, str | None]] = []
        self.undismiss_calls: list[tuple[UUID, str]] = []
        self.list_calls: list[UUID] = []

    async def dismiss(
        self,
        novel_id: UUID,
        fingerprint: str,
        reason: str | None = None,
    ) -> None:
        self.dismiss_calls.append((novel_id, fingerprint, reason))
        self._store[(novel_id, fingerprint)] = reason

    async def list_dismissed(self, novel_id: UUID) -> list[str]:
        self.list_calls.append(novel_id)
        return [fp for (nid, fp) in self._store if nid == novel_id]

    async def undismiss(self, novel_id: UUID, fingerprint: str) -> bool:
        self.undismiss_calls.append((novel_id, fingerprint))
        return self._store.pop((novel_id, fingerprint), None) is not None


def make_dismissed_ownership_service(
    ownership: dict[UUID, UUID],
    novel_id: UUID | None = None,
    fingerprints: list[str] | None = None,
) -> tuple[DismissedFindingService, RecordingDismissedRepo, FakeNovelRepo]:
    """Build a DismissedFindingService over recording fakes + an ownership map.

    ``fingerprints`` seeds pre-existing dismissals under ``novel_id``
    (for list reads). No feedback memory: the mem0 forward is a
    post-persist extra — the ownership matrix asserts the DB dismissal
    state, which is the source of truth.
    """
    from narrare.kb.dismissed_service import DismissedFindingService

    novel_repo = FakeNovelRepo(ownership)
    repo = RecordingDismissedRepo(novel_id, fingerprints)
    service = DismissedFindingService(
        cast("DismissedFindingRepositoryProtocol", repo),
        cast("NovelRepositoryProtocol", novel_repo),
    )
    return service, repo, novel_repo


# ---------------------------------------------------------------------------
# Extraction fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeExtractionChapter:
    """Minimal chapter-like object (content + title are all the service reads)."""

    id: UUID = field(default_factory=uuid4)
    content: str = "Aria entered the room."
    title: str = "Chapter 1"


class RecordingExtractionChapterRepo:
    """Fake ChapterRepositoryProtocol — records chapter content loads."""

    def __init__(self, chapter: FakeExtractionChapter | None) -> None:
        self._chapter = chapter
        self.get_by_id_calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, chapter_id: UUID, novel_id: UUID) -> FakeExtractionChapter | None:
        self.get_by_id_calls.append((chapter_id, novel_id))
        return self._chapter


class RecordingExtractionKBRepo:
    """Fake KBRepositoryProtocol — records dedup/world-context entry reads."""

    def __init__(self) -> None:
        self.list_entries_calls: list[UUID] = []

    async def list_entries(
        self,
        novel_id: UUID,
        **_kwargs: object,
    ) -> tuple[list[object], int]:
        self.list_entries_calls.append(novel_id)
        return [], 0


class CountingModelRegistry:
    """Fake ModelRegistry — counts model resolution (LLM boundary)."""

    def __init__(self) -> None:
        self.get_model_calls: int = 0

    async def get_model(self, _config: object) -> object:
        self.get_model_calls += 1
        return object()

    async def prepare(
        self,
        config: object,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Task-6d bridge: prepare delegates to the SAME counted get_model."""
        from typing import cast as _cast

        from narrare_core.llm._prepared_call import PreparedModelCall

        return PreparedModelCall(
            model=_cast("Model", await self.get_model(config)),
            model_settings=None,
            usage_limits=None,
        )


class CountingComposer:
    """Fake PromptComposer — records prompt builds."""

    def __init__(self) -> None:
        self.build_calls: list[object] = []

    async def build(self, intent: object, _context: object) -> ComposedPrompt:
        self.build_calls.append(intent)
        return ComposedPrompt(system="stub system prompt.", user="stub user prompt.")


def make_extraction_ownership_service(
    ownership: dict[UUID, UUID],
    chapter: FakeExtractionChapter | None,
    config: ResolvedModelConfig,
) -> tuple[
    ExtractionService,
    RecordingExtractionChapterRepo,
    RecordingExtractionKBRepo,
    CountingModelRegistry,
    CountingComposer,
    FakeNovelRepo,
]:
    """Build an ExtractionService over recording fakes + an ownership map."""
    from narrare.kb.extraction_service import ExtractionService

    from ._extraction_helpers import static_resolution

    novel_repo = FakeNovelRepo(ownership)
    chapter_repo = RecordingExtractionChapterRepo(chapter)
    kb_repo = RecordingExtractionKBRepo()
    registry = CountingModelRegistry()
    composer = CountingComposer()
    service = ExtractionService(
        registry=cast("ModelRegistry", registry),
        model_resolution=static_resolution(config),
        chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        composer=cast("PromptComposer", composer),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
    )
    return service, chapter_repo, kb_repo, registry, composer, novel_repo


__all__ = [
    "CountingComposer",
    "CountingModelRegistry",
    "FakeExtractionChapter",
    "FakeRelEntry",
    "FakeRelRow",
    "RecordingDismissedRepo",
    "RecordingExtractionChapterRepo",
    "RecordingExtractionKBRepo",
    "RecordingRelEntryRepo",
    "RecordingRelRepo",
    "make_dismissed_ownership_service",
    "make_extraction_ownership_service",
    "make_relationship_ownership_service",
]
