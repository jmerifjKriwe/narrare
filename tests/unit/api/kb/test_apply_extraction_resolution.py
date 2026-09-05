"""Unit tests for extraction apply — update_entity target resolution & rename.

Service-level integration of the entity-resolution behavior (KB-007): the
pure resolution unit tests live in test_extraction_resolution.py, the base
update path in test_apply_extraction.py.

Scenarios (RULE-20):
1. Fuller name on an ID-referenced update → persisted rename
2. Strict-substring proposal → downgrade blocked, update still lands
3. No target ID + exact name match → repair-path resolution
4. No target ID + distractor/unknown name → skipped
5. Entity-type mismatch (ID path) → skipped
6. Hallucinated non-UUID target ID → logged skip, not a crash
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast
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
    from typing import Any

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.service import KBService


def _item(
    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"] = "update_entity",
    name: str = "Anna Meyer",
    entity_type: str | None = "character",
    proposed_content: dict[str, Any] | None = None,
    target_entity_id: str | None = None,
    source_text: str = "test source",
) -> ApplyExtractionItem:
    return ApplyExtractionItem(
        item_type=item_type,
        name=name,
        entity_type=entity_type,
        proposed_content=proposed_content,
        target_entity_id=target_entity_id,
        source_text=source_text,
    )


# ---------------------------------------------------------------------------
# Fixtures (re-imported fakes, local fixtures — see test_apply_extraction)
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


# ---------------------------------------------------------------------------
# Rename via validated target ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_update_entity_renames_entry(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
    fake_kb_repo: _FakeKBRepoForApply,
) -> None:
    """A fuller name on an ID-referenced update is persisted as a rename."""
    novel_id = uuid4()
    entry_id = uuid4()
    fake_kb_service.seed("Anna", entry_id=entry_id)
    fake_kb_repo.seed("Anna", entry_id=entry_id, novel_id=novel_id)
    items = [
        _item(
            name="Anna Meyer",
            target_entity_id=str(entry_id),
            proposed_content={"role": "protagonist"},
        ),
    ]

    result = await apply_service.apply(novel_id=novel_id, user_id=uuid4(), items=items)

    assert len(result.updated_entries) == 1
    data = fake_kb_service.updated[0]["data"]
    assert cast("Any", data).name == "Anna Meyer"
    assert cast("Any", data).metadata == {"role": "protagonist"}


@pytest.mark.asyncio
async def test_apply_update_entity_downgrade_rename_blocked(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
    fake_kb_repo: _FakeKBRepoForApply,
) -> None:
    """A strict-substring proposal does not narrow the canonical name."""
    novel_id = uuid4()
    entry_id = uuid4()
    fake_kb_service.seed("Anna Meyer", entry_id=entry_id)
    fake_kb_repo.seed("Anna Meyer", entry_id=entry_id, novel_id=novel_id)
    items = [
        _item(
            name="Anna",
            target_entity_id=str(entry_id),
            proposed_content={"status": "deceased"},
        ),
    ]

    result = await apply_service.apply(novel_id=novel_id, user_id=uuid4(), items=items)

    # Update still lands (metadata), but without the regressive rename.
    assert len(result.updated_entries) == 1
    data = fake_kb_service.updated[0]["data"]
    assert cast("Any", data).name is None


# ---------------------------------------------------------------------------
# Exact-name repair path (no target ID)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_update_entity_resolves_by_name_without_target_id(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
    fake_kb_repo: _FakeKBRepoForApply,
) -> None:
    """Without target ID, an exact name match repairs the dead update path."""
    novel_id = uuid4()
    entry = fake_kb_repo.seed("Anna", novel_id=novel_id)
    items = [
        _item(
            name="Anna",
            target_entity_id=None,
            proposed_content={"status": "traveling"},
        ),
    ]

    result = await apply_service.apply(novel_id=novel_id, user_id=uuid4(), items=items)

    assert len(result.updated_entries) == 1
    assert fake_kb_service.updated[0]["target_entry_id"] == entry.id


@pytest.mark.asyncio
async def test_apply_update_entity_unknown_name_without_target_id_skipped(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
    fake_kb_repo: _FakeKBRepoForApply,
) -> None:
    """A distractor name ("Anna Meier" vs KB "Anna") does not resolve."""
    novel_id = uuid4()
    fake_kb_repo.seed("Anna", novel_id=novel_id)
    items = [_item(name="Anna Meier", target_entity_id=None)]

    result = await apply_service.apply(novel_id=novel_id, user_id=uuid4(), items=items)

    assert len(result.updated_entries) == 0
    assert len(fake_kb_service.updated) == 0


# ---------------------------------------------------------------------------
# Blocking guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_update_entity_type_mismatch_skipped(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
    fake_kb_repo: _FakeKBRepoForApply,
) -> None:
    """An item whose entity_type differs from the entry is not matched."""
    novel_id = uuid4()
    entry_id = uuid4()
    fake_kb_repo.seed("Anna", entity_type="character", entry_id=entry_id, novel_id=novel_id)
    items = [
        _item(
            name="Anna Meyer",
            entity_type="location",
            target_entity_id=str(entry_id),
        ),
    ]

    result = await apply_service.apply(novel_id=novel_id, user_id=uuid4(), items=items)

    assert len(result.updated_entries) == 0
    assert len(fake_kb_service.updated) == 0


@pytest.mark.asyncio
async def test_apply_update_entity_invalid_target_id_skipped(
    apply_service: ExtractionApplyService,
    fake_kb_service: _FakeKBService,
    fake_kb_repo: _FakeKBRepoForApply,
) -> None:
    """A hallucinated non-UUID target ID is a logged skip, not a crash."""
    novel_id = uuid4()
    fake_kb_repo.seed("Anna", novel_id=novel_id)
    items = [_item(name="Anna", target_entity_id="id-from-existing-list")]

    result = await apply_service.apply(novel_id=novel_id, user_id=uuid4(), items=items)

    assert len(result.updated_entries) == 0
    assert len(fake_kb_service.updated) == 0
