"""Unit tests for relationship endpoint resolution in the apply flow.

Regression tests for the scoring-diagnosis dead path: relationship items
used to resolve their source via ``name``, which the extraction prompt
defined as a human-readable relationship label ("Anna engaged to Peter") —
so every relationship item hit ``source_not_found`` and was silently dropped.

New contract (prompt v1.4.0): ``name`` carries the predicate;
``source_entity_name``/``target_entity_name`` identify both endpoints.
Legacy payloads (``name`` = source entity name, ``related_entity_name`` =
target) must keep working.

Also covers skip reporting: every unapplied item is reported in
``ApplyExtractionResponse.skipped`` with a machine-readable reason —
no silent drops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
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


@pytest.fixture
def fake_kb_repo() -> _FakeKBRepoForApply:
    return _FakeKBRepoForApply()


@pytest.fixture
def fake_rel_repo() -> _FakeRelationshipRepo:
    return _FakeRelationshipRepo()


@pytest.fixture
def apply_service(
    fake_rel_repo: _FakeRelationshipRepo,
    fake_kb_repo: _FakeKBRepoForApply,
) -> ExtractionApplyService:
    return _service(fake_rel_repo, fake_kb_repo)


def _service(
    fake_rel_repo: _FakeRelationshipRepo,
    fake_kb_repo: _FakeKBRepoForApply,
    fake_kb_service: _FakeKBService | None = None,
) -> ExtractionApplyService:
    return ExtractionApplyService(
        kb_service=cast("KBService", fake_kb_service or _FakeKBService()),
        rel_repo=cast("RelationshipRepository", fake_rel_repo),
        kb_repo=cast("KBRepositoryProtocol", fake_kb_repo),
    )


# ---------------------------------------------------------------------------
# New contract: explicit endpoint names
# ---------------------------------------------------------------------------


class TestNewContractEndpointResolution:
    """Relationship items resolve source/target via explicit name fields."""

    @pytest.mark.asyncio
    async def test_relationship_with_endpoint_names_creates_edge(
        self,
        fake_kb_repo: _FakeKBRepoForApply,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """name=predicate + source/target names resolves both endpoints."""
        anna = fake_kb_repo.seed("Anna Meyer", entity_type="character")
        peter = fake_kb_repo.seed("Peter Meyer", entity_type="character")
        service = _service(fake_rel_repo, fake_kb_repo)

        items = [
            ApplyExtractionItem(
                item_type="relationship",
                name="engaged_to",
                relationship_type="engaged_to",
                source_entity_name="Anna Meyer",
                target_entity_name="Peter Meyer",
                source_text="Anna engaged to Peter.",
            ),
        ]

        result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(fake_rel_repo.created) == 1
        rel = cast("Any", fake_rel_repo.created[0])
        assert rel.source_id == anna.id
        assert rel.target_id == peter.id
        assert rel.rel_type == "engaged_to"
        assert result.skipped == []

    @pytest.mark.asyncio
    async def test_target_entity_name_takes_precedence_over_related_name(
        self,
        fake_kb_repo: _FakeKBRepoForApply,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """Explicit target_entity_name beats legacy related_entity_name."""
        anna = fake_kb_repo.seed("Anna", entity_type="character")
        peter = fake_kb_repo.seed("Peter", entity_type="character")
        fake_kb_repo.seed("Kael", entity_type="character")
        service = _service(fake_rel_repo, fake_kb_repo)

        items = [
            ApplyExtractionItem(
                item_type="relationship",
                name="engaged_to",
                relationship_type="engaged_to",
                source_entity_name="Anna",
                target_entity_name="Peter",
                related_entity_name="Kael",
                source_text="Anna engaged to Peter.",
            ),
        ]

        await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(fake_rel_repo.created) == 1
        rel = cast("Any", fake_rel_repo.created[0])
        assert rel.target_id == peter.id
        assert rel.source_id == anna.id


# ---------------------------------------------------------------------------
# Backward compatibility: legacy payload shape
# ---------------------------------------------------------------------------


class TestLegacyPayloadCompat:
    """Legacy items (name = source entity, related_entity_name = target)."""

    @pytest.mark.asyncio
    async def test_legacy_name_and_related_name_still_resolve(
        self,
        fake_kb_repo: _FakeKBRepoForApply,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """Without endpoint names, name/related_entity_name are the fallbacks."""
        anna = fake_kb_repo.seed("Anna", entity_type="character")
        forest = fake_kb_repo.seed("Dark Forest", entity_type="location")
        service = _service(fake_rel_repo, fake_kb_repo)

        items = [
            ApplyExtractionItem(
                item_type="relationship",
                name="Anna",
                relationship_type="located_at",
                related_entity_name="Dark Forest",
                source_text="Anna lives near the Dark Forest.",
            ),
        ]

        result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(fake_rel_repo.created) == 1
        rel = cast("Any", fake_rel_repo.created[0])
        assert rel.source_id == anna.id
        assert rel.target_id == forest.id
        assert result.skipped == []


# ---------------------------------------------------------------------------
# Skip reporting — no silent drops
# ---------------------------------------------------------------------------


class TestRelationshipSkipReporting:
    """Failed relationship items are reported in response.skipped."""

    @pytest.mark.asyncio
    async def test_source_not_found_reported_in_skipped(
        self,
        fake_kb_repo: _FakeKBRepoForApply,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """Unknown source entity → skipped entry with reason source_not_found."""
        fake_kb_repo.seed("Peter Meyer", entity_type="character")
        service = _service(fake_rel_repo, fake_kb_repo)

        items = [
            ApplyExtractionItem(
                item_type="relationship",
                name="engaged_to",
                relationship_type="engaged_to",
                source_entity_name="Nobody",
                target_entity_name="Peter Meyer",
            ),
        ]

        result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(fake_rel_repo.created) == 0
        assert len(result.skipped) == 1
        skip = result.skipped[0]
        assert skip.name == "engaged_to"
        assert skip.item_type == "relationship"
        assert skip.reason == "source_not_found"

    @pytest.mark.asyncio
    async def test_target_not_found_reported_in_skipped(
        self,
        fake_kb_repo: _FakeKBRepoForApply,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """Unknown target entity → skipped entry with reason target_not_found."""
        fake_kb_repo.seed("Anna Meyer", entity_type="character")
        service = _service(fake_rel_repo, fake_kb_repo)

        items = [
            ApplyExtractionItem(
                item_type="relationship",
                name="engaged_to",
                relationship_type="engaged_to",
                source_entity_name="Anna Meyer",
                target_entity_name="Nobody",
            ),
        ]

        result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(fake_rel_repo.created) == 0
        assert len(result.skipped) == 1
        assert result.skipped[0].reason == "target_not_found"

    @pytest.mark.asyncio
    async def test_missing_relationship_type_reported_in_skipped(
        self,
        fake_kb_repo: _FakeKBRepoForApply,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """Relationship item without relationship_type → skip with reason."""
        fake_kb_repo.seed("Anna", entity_type="character")
        fake_kb_repo.seed("Peter", entity_type="character")
        service = _service(fake_rel_repo, fake_kb_repo)

        items = [
            ApplyExtractionItem(
                item_type="relationship",
                name="engaged_to",
                relationship_type=None,
                source_entity_name="Anna",
                target_entity_name="Peter",
            ),
        ]

        result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(fake_rel_repo.created) == 0
        assert len(result.skipped) == 1
        assert result.skipped[0].reason == "missing_relationship_type"

    @pytest.mark.asyncio
    async def test_missing_endpoint_names_reported_in_skipped(
        self,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """No resolvable endpoint names at all → skip with reason."""
        service = _service(fake_rel_repo, _FakeKBRepoForApply())

        items = [
            ApplyExtractionItem(
                item_type="relationship",
                name="engaged_to",
                relationship_type="engaged_to",
            ),
        ]

        result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(fake_rel_repo.created) == 0
        assert len(result.skipped) == 1
        assert result.skipped[0].reason == "missing_source_or_target_name"


class TestOtherSkipReporting:
    """Unapplied non-relationship items are also reported (no silent drops)."""

    @pytest.mark.asyncio
    async def test_unresolvable_update_entity_reported_in_skipped(
        self,
        apply_service: ExtractionApplyService,
    ) -> None:
        """update_entity whose target cannot be resolved → skipped entry."""
        items = [
            ApplyExtractionItem(
                item_type="update_entity",
                name="No Target",
            ),
        ]

        result = await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(result.updated_entries) == 0
        assert len(result.skipped) == 1
        assert result.skipped[0].name == "No Target"
        assert result.skipped[0].item_type == "update_entity"
        assert result.skipped[0].reason == "target_not_resolved"

    @pytest.mark.asyncio
    async def test_failing_item_reported_in_skipped(
        self,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """An item raising inside apply is reported, not silently dropped."""
        fake_kb_service = _FakeKBService()
        fake_kb_service.fail_next_create = True
        service = _service(fake_rel_repo, _FakeKBRepoForApply(), fake_kb_service)

        items = [
            ApplyExtractionItem(
                item_type="new_entity",
                name="Doomed Entity",
                entity_type="character",
            ),
        ]

        result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(result.created_entries) == 0
        assert len(result.skipped) == 1
        assert result.skipped[0].name == "Doomed Entity"
        assert result.skipped[0].reason.startswith("exception:")

    @pytest.mark.asyncio
    async def test_conflict_acknowledged_is_not_a_skip(
        self,
        apply_service: ExtractionApplyService,
    ) -> None:
        """Conflict items are acknowledged by design — not reported as skipped."""
        items = [
            ApplyExtractionItem(item_type="conflict", name="Timeline Discrepancy"),
        ]

        result = await apply_service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert result.skipped == []

    @pytest.mark.asyncio
    async def test_mixed_batch_reports_applied_and_skipped(
        self,
        fake_kb_repo: _FakeKBRepoForApply,
        fake_rel_repo: _FakeRelationshipRepo,
    ) -> None:
        """Applied items land in created/updated; failures land in skipped."""
        fake_kb_repo.seed("Anna", entity_type="character")
        service = _service(fake_rel_repo, fake_kb_repo)

        items = [
            ApplyExtractionItem(
                item_type="relationship",
                name="engaged_to",
                relationship_type="engaged_to",
                source_entity_name="Anna",
                target_entity_name="Anna",
            ),
            ApplyExtractionItem(
                item_type="relationship",
                name="sibling_of",
                relationship_type="sibling_of",
                source_entity_name="Anna",
                target_entity_name="Nobody",
            ),
        ]

        result = await service.apply(novel_id=uuid4(), user_id=uuid4(), items=items)

        assert len(fake_rel_repo.created) == 1
        assert len(result.skipped) == 1
        assert result.skipped[0].reason == "target_not_found"
