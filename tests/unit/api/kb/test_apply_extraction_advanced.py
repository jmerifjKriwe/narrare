"""Unit tests for extraction apply — edge cases and advanced scenarios.

Split from test_apply_extraction.py per RULE-04 (file size limit).

Tests:
4. Conflict items → skipped, no error
5. Empty items → empty response
6. Mixed items → all types handled correctly
7. One item fails, others proceed
8. ExtractionService delegation
9. ExtractionService without dependencies raises ValueError
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from narrare.kb.extraction_apply_service import ExtractionApplyService
from narrare.kb.extraction_service import ExtractionService
from narrare.kb.schemas_extraction import ApplyExtractionItem, ApplyExtractionResponse
from narrare_core.llm import ResolvedModelConfig

if TYPE_CHECKING:
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.service import KBService
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

# Fakes live in the shared helpers module (RULE-04 extraction)
from ._apply_extraction_helpers import (
    _FakeKBRepoForApply,
    _FakeKBService,
    _FakeRelationshipRepo,
)


def _item(
    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"] = "new_entity",
    name: str = "Test Entity",
    entity_type: str | None = "character",
    proposed_content: dict[str, object] | None = None,
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
# Test 4: conflict items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_conflict_skipped(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
    fake_rel_repo: _FakeRelationshipRepo,
) -> None:
    """A conflict item is acknowledged and skipped (no DB changes)."""
    items = [
        _item(
            item_type="conflict",
            name="Timeline Discrepancy",
            source_text="The event happened in 1842 but KB says 1845",
        ),
    ]

    result = await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert len(result.created_entries) == 0
    assert len(result.updated_entries) == 0
    assert len(fake_kb_service.created) == 0
    assert len(fake_rel_repo.created) == 0


# ---------------------------------------------------------------------------
# Test 5: empty items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_empty_items_returns_empty_response(
    apply_service: ExtractionApplyService,
) -> None:
    """Empty items list returns an ApplyExtractionResponse with no entries."""
    result = await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=[])

    assert isinstance(result, ApplyExtractionResponse)
    assert len(result.created_entries) == 0
    assert len(result.updated_entries) == 0


# ---------------------------------------------------------------------------
# Test 6: mixed items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_mixed_items_handles_all_types(
    fake_kb_repo: _FakeKBRepoForApply,
    fake_rel_repo: _FakeRelationshipRepo,
) -> None:
    """Mixed item types are all handled correctly."""
    novel_id = uuid4()
    existing_id = uuid4()
    fake_kb_service = _FakeKBService()
    fake_kb_repo.seed("Anna", entity_type="character", novel_id=novel_id)
    fake_kb_repo.seed("Dark Forest", entity_type="location", novel_id=novel_id)
    fake_kb_repo.seed("Existing One", entry_id=existing_id, novel_id=novel_id)
    fake_kb_service.seed("Existing One", entry_id=existing_id)

    service = ExtractionApplyService(
        kb_service=cast("KBService", fake_kb_service),
        rel_repo=cast("RelationshipRepository", fake_rel_repo),
        kb_repo=cast("KBRepositoryProtocol", fake_kb_repo),
    )

    items = [
        _item(item_type="new_entity", name="New Character", entity_type="character"),
        _item(
            item_type="update_entity",
            name="Existing One",
            target_entity_id=str(existing_id),
            proposed_content={"age": 30},
        ),
        _item(
            item_type="relationship",
            name="Anna",
            related_entity_name="Dark Forest",
            relationship_type="explores",
        ),
        _item(item_type="conflict", name="Some Conflict"),
    ]

    result = await service.apply(novel_id=novel_id, user_id=uuid4(), items=items)

    assert len(result.created_entries) == 1
    assert len(result.updated_entries) == 1
    assert len(fake_kb_service.created) == 1
    assert len(fake_kb_service.updated) == 1
    assert len(fake_rel_repo.created) == 1


# ---------------------------------------------------------------------------
# Test 7: one item fails, others proceed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_one_item_fails_others_proceed(
    fake_rel_repo: _FakeRelationshipRepo,
    fake_kb_repo: _FakeKBRepoForApply,
) -> None:
    """When one item fails, remaining items are still applied."""
    fake_kb_service = _FakeKBService()
    fake_kb_service.fail_next_create = True

    service = ExtractionApplyService(
        kb_service=cast("KBService", fake_kb_service),
        rel_repo=cast("RelationshipRepository", fake_rel_repo),
        kb_repo=cast("KBRepositoryProtocol", fake_kb_repo),
    )

    items = [
        _item(item_type="new_entity", name="Fail Item", entity_type="character"),
        _item(item_type="new_entity", name="Success Item", entity_type="location"),
    ]

    result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    # First item failed, second succeeded
    assert len(result.created_entries) == 1
    assert result.created_entries[0].name == "Success Item"
    assert len(fake_kb_service.created) == 1


# ---------------------------------------------------------------------------
# Test 8: ExtractionService delegation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extraction_service_delegates_to_apply_service() -> None:
    """ExtractionService.apply_extraction delegates to ExtractionApplyService."""
    registry = AsyncMock()
    registry.get_model = AsyncMock(return_value=AsyncMock())
    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=4096,
    )
    chapter_repo = AsyncMock()
    kb_repo = _FakeKBRepoForApply()
    composer = AsyncMock()
    kb_service = _FakeKBService()
    rel_repo = _FakeRelationshipRepo()

    service = ExtractionService(
        registry=cast("ModelRegistry", registry),
        config=config,
        chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        composer=cast("PromptComposer", composer),
        kb_service=cast("KBService", kb_service),
        rel_repo=cast("RelationshipRepository", rel_repo),
    )

    items = [
        _item(item_type="new_entity", name="Delegated Entity", entity_type="character"),
    ]
    result = await service.apply_extraction(
        novel_id=uuid4(),
        user_id=uuid4(),
        items=items,
    )

    assert len(result.created_entries) == 1
    assert result.created_entries[0].name == "Delegated Entity"
    assert len(kb_service.created) == 1


@pytest.mark.asyncio
async def test_extraction_service_apply_without_deps_raises() -> None:
    """ExtractionService.apply_extraction raises ValueError when deps missing."""
    registry = AsyncMock()
    registry.get_model = AsyncMock(return_value=AsyncMock())
    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=4096,
    )
    chapter_repo = AsyncMock()
    kb_repo = _FakeKBRepoForApply()
    composer = AsyncMock()

    # kb_service and rel_repo are NOT provided
    service = ExtractionService(
        registry=cast("ModelRegistry", registry),
        config=config,
        chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        composer=cast("PromptComposer", composer),
    )

    with pytest.raises(ValueError, match="KBService and RelationshipRepository"):
        await service.apply_extraction(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[_item(item_type="new_entity", name="Test")],
        )


# ---------------------------------------------------------------------------
# Fixtures (re-exported from main module for shared use)
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
