"""Regression tests for the apply-path data-loss bug (benchmark run 5).

Root-cause chain diagnosed from benchmark run 5 (33 of 64 created entities
vanished server-side while the response reported 200 + created_entries):

1. Fix A — relationship idempotency: re-proposed edges (e.g. ``engaged_to``
   Anna→Peter in ch-03, already created in ch-01) hit the
   ``uq_kb_relationships_unique`` constraint → asyncpg UniqueViolation →
   SQLAlchemy IntegrityError. A duplicate apply must be acknowledged as
   success instead of inserting (or raising).
2. Fix B — SAVEPOINT per item: the per-item ``except`` caught the error but
   the session stayed poisoned (PendingRollbackError) → every subsequent
   item failed AND the request-final commit rolled back the whole batch.
   Each item must be applied inside a savepoint so a failing item rolls
   back only itself.
3. Fix C — in-batch entity resolution: relationships referencing entities
   CREATED EARLIER IN THE SAME apply-request failed with
   ``source_lookup_failed`` (the resolver only saw pre-request state).
   Endpoint resolution must consult the request's created entries too.

The response was built from in-memory objects BEFORE the failed commit —
reporting "created N" while the DB had 0. Fix B makes the final commit
succeed, so the response becomes truthful.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.kb.extraction_apply_service import ExtractionApplyService
from narrare.kb.schemas_extraction import ApplyExtractionItem

from ._apply_extraction_helpers import (
    _FakeApplySession,
    _FakeKBRepoForApply,
    _FakeKBService,
    _FakeRelationshipRepo,
)

if TYPE_CHECKING:
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.service import KBService


def _relationship_item(
    source: str,
    target: str,
    rel_type: str = "engaged_to",
) -> ApplyExtractionItem:
    return ApplyExtractionItem(
        item_type="relationship",
        name=rel_type,
        relationship_type=rel_type,
        source_entity_name=source,
        target_entity_name=target,
        source_text=f"{source} {rel_type} {target}.",
    )


def _service(
    rel_repo: _FakeRelationshipRepo,
    kb_repo: _FakeKBRepoForApply,
    kb_service: _FakeKBService | None = None,
    session: _FakeApplySession | None = None,
) -> ExtractionApplyService:
    return ExtractionApplyService(
        kb_service=cast("KBService", kb_service or _FakeKBService()),
        rel_repo=cast("RelationshipRepository", rel_repo),
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        session=cast("AsyncSession", session or _FakeApplySession()),
    )


# ---------------------------------------------------------------------------
# Test A — Fix A: relationship idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_relationship_second_apply_acknowledged_one_edge() -> None:
    """Applying the same relationship twice → second apply is a success
    (no skip entry, no exception) and still exactly 1 edge exists."""
    kb_repo = _FakeKBRepoForApply()
    kb_repo.seed("Anna", entity_type="character")
    kb_repo.seed("Peter", entity_type="character")
    rel_repo = _FakeRelationshipRepo()
    service = _service(rel_repo, kb_repo)

    item = _relationship_item("Anna", "Peter", "engaged_to")

    first = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=[item])
    second = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=[item])

    assert first.skipped == []
    assert second.skipped == []
    assert len(rel_repo.created) == 1


# ---------------------------------------------------------------------------
# Test C — Fix C: in-batch entity resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relationship_resolves_entity_created_earlier_in_batch() -> None:
    """A relationship referencing an entity created earlier in the SAME
    apply-request resolves against that in-batch creation and applies."""
    kb_repo = _FakeKBRepoForApply()
    kb_repo.seed("Anna", entity_type="character")
    rel_repo = _FakeRelationshipRepo()
    kb_service = _FakeKBService()
    service = _service(rel_repo, kb_repo, kb_service)

    items = [
        ApplyExtractionItem(
            item_type="new_entity",
            name="X",
            entity_type="character",
            source_text="X appears.",
        ),
        _relationship_item("X", "Anna", "colleague_of"),
    ]

    result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    assert result.skipped == []
    assert len(result.created_entries) == 1
    assert len(rel_repo.created) == 1
    rel = cast("Any", rel_repo.created[0])
    created_id = result.created_entries[0].id
    assert str(rel.source_id) == created_id


# ---------------------------------------------------------------------------
# Test B — Fix B: SAVEPOINT per item, batch survives a failing item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failing_item_rolls_back_only_itself_batch_survives() -> None:
    """Item 2 raises IntegrityError → its savepoint rolls back, items
    1/3/4 still apply, and only the failing item is reported skipped."""
    kb_repo = _FakeKBRepoForApply()
    kb_repo.seed("Anna", entity_type="character")
    kb_repo.seed("Peter", entity_type="character")
    kb_repo.seed("Paula", entity_type="character")
    rel_repo = _FakeRelationshipRepo()
    rel_repo.fail_on_rel_types = {"poisoned_to"}
    kb_service = _FakeKBService()
    session = _FakeApplySession()
    service = _service(rel_repo, kb_repo, kb_service, session)

    items = [
        _relationship_item("Anna", "Peter", "engaged_to"),
        _relationship_item("Anna", "Paula", "poisoned_to"),
        _relationship_item("Peter", "Paula", "colleague_of"),
        ApplyExtractionItem(
            item_type="new_entity",
            name="Late Arrival",
            entity_type="character",
            source_text="Late Arrival appears.",
        ),
    ]

    result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

    # Only item 2 is skipped; the reported reason carries the exception.
    assert len(result.skipped) == 1
    assert result.skipped[0].name == "poisoned_to"
    assert result.skipped[0].reason.startswith("exception:")

    # Items 1 and 3 committed their edges; item 4 committed its entry.
    assert len(rel_repo.created) == 2
    assert len(kb_service.created) == 1
    assert result.created_entries[0].name == "Late Arrival"

    # Every item ran inside its own savepoint; exactly one rolled back.
    assert session.begun == 4
    assert session.rollbacks == 1
