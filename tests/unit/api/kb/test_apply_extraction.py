"""Unit tests for extraction apply — saving endorsed items to the KB.

Tests ExtractionApplyService directly for detailed behavior, and
ExtractionService.apply_extraction() for correct delegation.

Scenarios (RULE-20):
1. new_entity items → creates KB entries
2. update_entity items → updates existing entries (rename/resolution
   scenarios: test_apply_extraction_resolution.py, pure resolution unit
   tests: test_extraction_resolution.py)
3. relationship items → creates relationships
4. conflict items → skipped, no error
5. Empty items → empty response
6. Mixed items → all types handled correctly
7. One item fails, others proceed
8. Missing dependencies raises ValueError
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import uuid4

import pytest

from narrare.kb.extraction_apply_service import ExtractionApplyService
from narrare.kb.schemas_extraction import ApplyExtractionItem

from ._apply_extraction_helpers import (
    _FakeKBRepoForApply,
    _FakeKBService,
    _FakeRelationshipRepo,
)

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.service import KBService

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
        kb_service=cast("KBService", fake_kb_service),
        rel_repo=cast("RelationshipRepository", fake_rel_repo),
        kb_repo=cast("KBRepositoryProtocol", fake_kb_repo),
    )


def _item(
    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"] = "new_entity",
    name: str = "Test Entity",
    entity_type: str | None = "character",
    proposed_content: dict[str, Any] | None = None,
    target_entity_id: str | None = None,
    relationship_type: str | None = None,
    related_entity_name: str | None = None,
    source_text: str = "test source",
) -> ApplyExtractionItem:
    return ApplyExtractionItem(
        item_type=item_type,
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
    assert cast("Any", created_data).metadata == proposed


# ---------------------------------------------------------------------------
# Test 2: update_entity items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_update_entity_updates_entry(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
    fake_kb_repo: _FakeKBRepoForApply,
) -> None:
    """An update_entity item updates an existing KB entry."""
    novel_id = uuid4()
    entry_id = uuid4()
    fake_kb_service.seed("Existing Character", entry_id=entry_id)
    fake_kb_repo.seed("Existing Character", entry_id=entry_id, novel_id=novel_id)
    items = [
        _item(
            item_type="update_entity",
            name="Existing Character",
            target_entity_id=str(entry_id),
            proposed_content={"status": "deceased"},
        ),
    ]

    result = await apply_service.apply(novel_id=novel_id, user_id=uuid4(), items=items)

    assert len(result.updated_entries) == 1
    assert result.updated_entries[0].name == "Existing Character"
    assert len(fake_kb_service.updated) == 1
    assert fake_kb_service.updated[0]["target_entry_id"] == entry_id


@pytest.mark.asyncio
async def test_apply_update_entity_missing_target_id_is_skipped(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
) -> None:
    """An update_entity item whose name matches no KB entry is skipped."""
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
        kb_service=cast("KBService", _FakeKBService()),
        rel_repo=cast("RelationshipRepository", fake_rel_repo),
        kb_repo=cast("KBRepositoryProtocol", fake_kb_repo),
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
        kb_service=cast("KBService", _FakeKBService()),
        rel_repo=cast("RelationshipRepository", fake_rel_repo),
        kb_repo=cast("KBRepositoryProtocol", fake_kb_repo),
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
