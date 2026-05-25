"""Unit tests for extraction apply — saving endorsed items to the KB.

Tests ExtractionApplyService directly for detailed behavior, and
ExtractionService.apply_extraction() for correct delegation.

Scenarios (RULE-20):
1. new_entity items → creates KB entries
2. update_entity items → updates existing entries
3. relationship items → creates relationships
4. conflict items → skipped, no error
5. Empty items → empty response
6. Mixed items → all types handled correctly
7. One item fails, others proceed
8. Missing dependencies raises ValueError
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from narrare.kb.extraction_apply_service import ExtractionApplyService
from narrare.kb.schemas_extraction import ApplyExtractionItem

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeEntry:
    """Minimal fake KB entry returned by FakeKBService."""

    def __init__(self, name: str, entity_type: str = "character") -> None:
        self.id = uuid4()
        self.name = name
        self.entity_type = entity_type


class _FakeKBService:
    """Fake KBService that records creates and updates."""

    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.updated: list[dict[str, object]] = []
        self.fail_next_create = False
        self.fail_next_update = False
        self._entry_index: dict[UUID, _FakeEntry] = {}

    def seed(
        self, name: str, entity_type: str = "character", entry_id: UUID | None = None
    ) -> _FakeEntry:
        """Pre-populate an entity for update lookups."""
        entry = _FakeEntry(name=name, entity_type=entity_type)
        if entry_id is not None:
            entry.id = entry_id
        self._entry_index[entry.id] = entry
        return entry

    async def create(
        self,
        novel_id: UUID,
        user_id: UUID,
        data: object,
    ) -> _FakeEntry:
        if self.fail_next_create:
            self.fail_next_create = False
            msg = "KB service create failed"
            raise RuntimeError(msg)

        entry_name = getattr(data, "name", "Unknown")
        entry_type = getattr(data, "entity_type", "unknown")
        entry = _FakeEntry(name=entry_name, entity_type=entry_type)
        self.created.append(
            {
                "novel_id": novel_id,
                "user_id": user_id,
                "data": data,
                "entry_id": entry.id,
            },
        )
        return entry

    async def update(
        self,
        novel_id: UUID,
        entry_id: UUID,
        user_id: UUID,
        data: object,
    ) -> _FakeEntry:
        if self.fail_next_update:
            self.fail_next_update = False
            msg = "KB service update failed"
            raise RuntimeError(msg)

        existing = self._entry_index.get(entry_id)
        entry_name = existing.name if existing else "Updated"
        entry_type = existing.entity_type if existing else "character"
        entry = _FakeEntry(name=entry_name, entity_type=entry_type)
        self.updated.append(
            {
                "novel_id": novel_id,
                "target_entry_id": entry_id,
                "user_id": user_id,
                "data": data,
                "returned_entry_id": entry.id,
            },
        )
        return entry


class _FakeRelationshipRepo:
    """Fake RelationshipRepository that records creates."""

    def __init__(self) -> None:
        self.created: list[object] = []

    async def create(self, rel: object) -> object:
        self.created.append(rel)
        return rel


class _FakeKBRepoForApply:
    """Fake KBRepositoryProtocol — name-based entity lookup."""

    def __init__(self) -> None:
        self._entries: dict[str, _FakeEntry] = {}

    def seed(self, name: str, entity_type: str = "character") -> _FakeEntry:
        entry = _FakeEntry(name=name, entity_type=entity_type)
        self._entries[name.lower()] = entry
        return entry

    async def get_by_name(self, novel_id: UUID, name: str) -> _FakeEntry | None:
        return self._entries.get(name.lower())

    # Stub to satisfy the KBRepositoryProtocol interface for extraction_service
    async def list_entries(
        self, *args: object, **kwargs: object
    ) -> tuple[list[dict[str, Any]], int]:
        return [], 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_kb_service() -> _FakeKBService:
    return _FakeKBService()


@pytest.fixture
def fake_rel_repo() -> _FakeRelationshipRepo:
    return _FakeRelationshipRepo()


@pytest.fixture
def fake_kb_repo() -> _FakeKBRepoForApply:
    return _FakeKBRepoForApply()


@pytest.fixture
def apply_service(
    fake_kb_service: _FakeKBService,
    fake_rel_repo: _FakeRelationshipRepo,
    fake_kb_repo: _FakeKBRepoForApply,
) -> ExtractionApplyService:
    return ExtractionApplyService(
        kb_service=fake_kb_service,  # type: ignore[arg-type]
        rel_repo=fake_rel_repo,  # type: ignore[arg-type]
        kb_repo=fake_kb_repo,  # type: ignore[arg-type]
    )


def _item(
    item_type: str = "new_entity",
    name: str = "Test Entity",
    entity_type: str | None = "character",
    proposed_content: dict[str, Any] | None = None,
    target_entity_id: str | None = None,
    relationship_type: str | None = None,
    related_entity_name: str | None = None,
    source_text: str = "test source",
) -> ApplyExtractionItem:
    return ApplyExtractionItem(
        item_type=item_type,  # type: ignore[arg-type]
        name=name,
        entity_type=entity_type,
        proposed_content=proposed_content,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        related_entity_name=related_entity_name,
        source_text=source_text,
    )


# ---------------------------------------------------------------------------
# Test 1: new_entity items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_new_entity_creates_entry(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
) -> None:
    """A new_entity item creates a KB entry via service."""
    items = [_item(item_type="new_entity", name="Dark Forest", entity_type="location")]

    result = await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert len(result.created_entries) == 1
    assert result.created_entries[0].name == "Dark Forest"
    assert result.created_entries[0].entity_type == "location"
    assert len(result.updated_entries) == 0
    assert len(fake_kb_service.created) == 1


@pytest.mark.asyncio
async def test_apply_new_entity_without_entity_type_defaults_to_unknown(
    apply_service: ExtractionApplyService,
) -> None:
    """A new_entity item without entity_type defaults to 'unknown'."""
    items = [_item(item_type="new_entity", name="Mystery", entity_type=None)]

    result = await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert len(result.created_entries) == 1
    assert result.created_entries[0].entity_type == "unknown"


@pytest.mark.asyncio
async def test_apply_new_entity_passes_proposed_content_as_metadata(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
) -> None:
    """proposed_content is passed as metadata to KBService.create()."""
    proposed: dict[str, object] = {"role": "antagonist", "age": 150}
    items = [
        _item(
            item_type="new_entity",
            name="Shadow King",
            proposed_content=proposed,
        ),
    ]

    await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    created_data = fake_kb_service.created[0]["data"]
    assert hasattr(created_data, "metadata")
    assert created_data.metadata == proposed  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test 2: update_entity items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_update_entity_updates_entry(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
) -> None:
    """An update_entity item updates an existing KB entry."""
    entry_id = uuid4()
    fake_kb_service.seed("Existing Character", entry_id=entry_id)
    items = [
        _item(
            item_type="update_entity",
            name="Existing Character",
            target_entity_id=str(entry_id),
            proposed_content={"status": "deceased"},
        ),
    ]

    result = await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert len(result.updated_entries) == 1
    assert result.updated_entries[0].name == "Existing Character"
    assert len(fake_kb_service.updated) == 1
    assert fake_kb_service.updated[0]["target_entry_id"] == entry_id


@pytest.mark.asyncio
async def test_apply_update_entity_missing_target_id_is_skipped(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
) -> None:
    """An update_entity item without target_entity_id is skipped."""
    items = [
        _item(
            item_type="update_entity",
            name="No Target",
            target_entity_id=None,
        ),
    ]

    result = await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert len(result.updated_entries) == 0
    assert len(fake_kb_service.updated) == 0


# ---------------------------------------------------------------------------
# Test 3: relationship items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_relationship_creates_relationship(
    fake_kb_repo: _FakeKBRepoForApply,
    fake_rel_repo: _FakeRelationshipRepo,
) -> None:
    """A relationship item creates a relationship between two entities."""
    fake_kb_repo.seed("Anna", entity_type="character")
    fake_kb_repo.seed("Dark Forest", entity_type="location")
    service = ExtractionApplyService(
        kb_service=_FakeKBService(),  # type: ignore[arg-type]
        rel_repo=fake_rel_repo,  # type: ignore[arg-type]
        kb_repo=fake_kb_repo,  # type: ignore[arg-type]
    )

    items = [
        _item(
            item_type="relationship",
            name="Anna",
            related_entity_name="Dark Forest",
            relationship_type="located_at",
        ),
    ]

    result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert len(result.created_entries) == 0
    assert len(result.updated_entries) == 0
    assert len(fake_rel_repo.created) == 1


@pytest.mark.asyncio
async def test_apply_relationship_missing_fields_skipped(
    apply_service: ExtractionApplyService,
    fake_rel_repo: _FakeRelationshipRepo,
) -> None:
    """A relationship item without required fields is skipped."""
    items = [
        _item(
            item_type="relationship",
            name="Anna",
            related_entity_name=None,
            relationship_type=None,
        ),
    ]

    await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert len(fake_rel_repo.created) == 0


@pytest.mark.asyncio
async def test_apply_relationship_source_not_found_skipped(
    fake_rel_repo: _FakeRelationshipRepo,
) -> None:
    """A relationship item with unknown source entity is skipped."""
    fake_kb_repo = _FakeKBRepoForApply()
    fake_kb_repo.seed("Dark Forest", entity_type="location")
    service = ExtractionApplyService(
        kb_service=_FakeKBService(),  # type: ignore[arg-type]
        rel_repo=fake_rel_repo,  # type: ignore[arg-type]
        kb_repo=fake_kb_repo,  # type: ignore[arg-type]
    )

    items = [
        _item(
            item_type="relationship",
            name="Unknown Entity",
            related_entity_name="Dark Forest",
            relationship_type="located_at",
        ),
    ]

    await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert len(fake_rel_repo.created) == 0
