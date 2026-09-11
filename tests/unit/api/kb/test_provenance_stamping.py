"""Unit tests for extraction provenance stamping (ADR-085 P2, spec §5).

The apply flow exclusively owns a reserved ``metadata["provenance"]`` block;
LLM proposals can never forge it, and chapter positions are resolved via the
chapter repository — never from client-supplied numbers (spec §9(b)).
Behaviors: forge-strip, create/update stamping, absent chapter → zero change,
rename appends a variant, old-shape requests stay valid, plus §9(a) validator
admission and §9(b) position resolution through the repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from narrare.kb._validators import validate_entry_metadata
from narrare.kb.extraction_apply_service import ExtractionApplyService
from narrare.kb.schemas_extraction import ApplyExtractionItem, ApplyExtractionRequest

from ._apply_extraction_helpers import (
    _FakeApplySession,
    _FakeChapterRepo,
    _FakeKBRepoForApply,
    _FakeKBService,
    _FakeRelationshipRepo,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.service import KBService


def _make_service(
    kb_service: _FakeKBService,
    kb_repo: _FakeKBRepoForApply,
) -> ExtractionApplyService:
    return ExtractionApplyService(
        kb_service=cast("KBService", kb_service),
        rel_repo=cast("RelationshipRepository", _FakeRelationshipRepo()),
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        session=cast("AsyncSession", _FakeApplySession()),
    )


def _new_entity_item(name: str, proposed: dict[str, object] | None) -> ApplyExtractionItem:
    return ApplyExtractionItem(
        item_type="new_entity",
        name=name,
        entity_type="character",
        proposed_content=proposed,
    )


def _update_entity_item(
    name: str,
    proposed: dict[str, object] | None,
    target_entity_id: str | None = None,
) -> ApplyExtractionItem:
    return ApplyExtractionItem(
        item_type="update_entity",
        name=name,
        entity_type="character",
        proposed_content=proposed,
        target_entity_id=target_entity_id,
    )


PROVENANCE_V1: dict[str, object] = {
    "chapters": [3],
    "first_seen_chapter": 3,
    "last_seen_chapter": 3,
    "name_variants": ["Anna"],
}


# (a) Forge guard — reserved keys are stripped from proposals


class TestForgeStrip:
    """LLM proposals can never forge or clobber reserved metadata keys."""

    @pytest.mark.asyncio
    async def test_new_entity_forged_provenance_is_stripped(self) -> None:
        kb_service = _FakeKBService()
        service = _make_service(kb_service, _FakeKBRepoForApply())
        forged = {"chapters": [99], "first_seen_chapter": 99, "name_variants": ["X"]}

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[
                _new_entity_item(
                    "Anna",
                    {"role": "hero", "provenance": forged, "resolution": {"merged": True}},
                ),
            ],
        )

        metadata = cast("Any", kb_service.created[0]["data"]).metadata
        assert metadata["role"] == "hero"
        assert "provenance" not in metadata
        assert "resolution" not in metadata

    @pytest.mark.asyncio
    async def test_update_entity_forged_provenance_is_stripped(self) -> None:
        kb_service = _FakeKBService()
        kb_repo = _FakeKBRepoForApply()
        kb_repo.seed("Anna", metadata={"role": "hero"})
        service = _make_service(kb_service, kb_repo)
        forged = {"chapters": [99], "last_seen_chapter": 99, "name_variants": ["X"]}

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[
                _update_entity_item("Anna", {"mood": "calm", "provenance": forged}),
            ],
        )

        metadata = cast("Any", kb_service.updated[0]["data"]).metadata
        assert metadata["mood"] == "calm"
        assert metadata["role"] == "hero"
        assert "provenance" not in metadata
        assert "resolution" not in metadata

    @pytest.mark.asyncio
    async def test_forged_provenance_cannot_survive_position_stamp(self) -> None:
        kb_service = _FakeKBService()
        service = _make_service(kb_service, _FakeKBRepoForApply())

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[
                _new_entity_item(
                    "Anna",
                    {"provenance": {"chapters": [99], "last_seen_chapter": 99}},
                ),
            ],
            chapter_position=3,
        )

        metadata = cast("Any", kb_service.created[0]["data"]).metadata
        provenance = cast("dict[str, object]", metadata["provenance"])
        assert provenance["chapters"] == [3]
        assert provenance["last_seen_chapter"] == 3


# (b)+(c) Stamping on create and update


class TestProvenanceStamping:
    """The apply flow stamps provenance only from resolved positions."""

    @pytest.mark.asyncio
    async def test_create_with_position_stamps_initial_provenance(self) -> None:
        kb_service = _FakeKBService()
        service = _make_service(kb_service, _FakeKBRepoForApply())

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[_new_entity_item("Anna", {"role": "hero"})],
            chapter_position=3,
        )

        metadata = cast("Any", kb_service.created[0]["data"]).metadata
        assert metadata["provenance"] == {
            "chapters": [3],
            "first_seen_chapter": 3,
            "last_seen_chapter": 3,
            "name_variants": ["Anna"],
        }

    @pytest.mark.asyncio
    async def test_update_with_position_appends_chapter(self) -> None:
        kb_service = _FakeKBService()
        kb_repo = _FakeKBRepoForApply()
        kb_repo.seed("Anna", metadata={"role": "hero", "provenance": dict(PROVENANCE_V1)})
        service = _make_service(kb_service, kb_repo)

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[_update_entity_item("Anna", {"mood": "calm"})],
            chapter_position=7,
        )

        metadata = cast("Any", kb_service.updated[0]["data"]).metadata
        assert metadata["provenance"] == {
            "chapters": [3, 7],
            "first_seen_chapter": 3,
            "last_seen_chapter": 7,
            "name_variants": ["Anna"],
        }
        assert metadata["role"] == "hero"
        assert metadata["mood"] == "calm"

    @pytest.mark.asyncio
    async def test_update_dedupes_and_sorts_repeated_chapter(self) -> None:
        kb_service = _FakeKBService()
        kb_repo = _FakeKBRepoForApply()
        kb_repo.seed(
            "Anna",
            metadata={
                "provenance": {
                    "chapters": [7, 3],
                    "first_seen_chapter": 3,
                    "last_seen_chapter": 7,
                    "name_variants": ["Anna"],
                },
            },
        )
        service = _make_service(kb_service, kb_repo)

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[_update_entity_item("Anna", None)],
            chapter_position=7,
        )

        provenance = cast(
            "dict[str, object]",
            cast("Any", kb_service.updated[0]["data"]).metadata["provenance"],
        )
        assert provenance["chapters"] == [3, 7]
        assert provenance["last_seen_chapter"] == 7

    @pytest.mark.asyncio
    async def test_update_without_proposal_stamps_without_clobber(self) -> None:
        kb_service = _FakeKBService()
        kb_repo = _FakeKBRepoForApply()
        kb_repo.seed("Anna", metadata={"role": "hero"})
        service = _make_service(kb_service, kb_repo)

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[_update_entity_item("Anna", None)],
            chapter_position=7,
        )

        metadata = cast("Any", kb_service.updated[0]["data"]).metadata
        assert metadata["role"] == "hero"
        assert metadata["provenance"] == {
            "chapters": [7],
            "first_seen_chapter": 7,
            "last_seen_chapter": 7,
            "name_variants": ["Anna"],
        }


# (d) Absent chapter position → zero behavior change


class TestNoPositionNoChange:
    """Applying without a chapter position never alters provenance."""

    @pytest.mark.asyncio
    async def test_create_without_position_has_no_provenance(self) -> None:
        kb_service = _FakeKBService()
        service = _make_service(kb_service, _FakeKBRepoForApply())

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[_new_entity_item("Anna", {"role": "hero"})],
        )

        metadata = cast("Any", kb_service.created[0]["data"]).metadata
        assert metadata == {"role": "hero"}

    @pytest.mark.asyncio
    async def test_update_without_position_keeps_provenance_untouched(self) -> None:
        kb_service = _FakeKBService()
        kb_repo = _FakeKBRepoForApply()
        kb_repo.seed("Anna", metadata={"role": "hero", "provenance": dict(PROVENANCE_V1)})
        service = _make_service(kb_service, kb_repo)

        await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[_update_entity_item("Anna", {"mood": "calm"})],
        )

        metadata = cast("Any", kb_service.updated[0]["data"]).metadata
        assert metadata["provenance"] == PROVENANCE_V1


# (e) Rename appends a name variant


class TestNameVariants:
    """A renamed update grows ``name_variants`` (dedupe, keep order)."""

    @pytest.mark.asyncio
    async def test_rename_appends_new_name_variant(self) -> None:
        novel_id = uuid4()
        kb_service = _FakeKBService()
        kb_repo = _FakeKBRepoForApply()
        entry = kb_repo.seed(
            "Anna",
            metadata={"provenance": dict(PROVENANCE_V1)},
            novel_id=novel_id,
        )
        service = _make_service(kb_service, kb_repo)

        await service.apply(
            novel_id=novel_id,
            user_id=uuid4(),
            items=[
                _update_entity_item(
                    "Anna the Brave",
                    None,
                    target_entity_id=str(entry.id),
                ),
            ],
            chapter_position=5,
        )

        data = cast("Any", kb_service.updated[0]["data"])
        assert data.name == "Anna the Brave"
        provenance = cast("dict[str, object]", data.metadata["provenance"])
        assert provenance["name_variants"] == ["Anna", "Anna the Brave"]


# (f) Backward compatibility + §9(a)/§9(b) verification


class TestBackwardCompatAndGates:
    """Old-shape requests stay valid; gates admit/resolve as specified."""

    def test_old_shape_request_without_chapter_id_is_valid(self) -> None:
        request = ApplyExtractionRequest.model_validate(
            {"items": [{"item_type": "new_entity", "name": "Anna"}]},
        )
        assert request.chapter_id is None

    def test_request_chapter_id_round_trips(self) -> None:
        chapter_id = uuid4()
        request = ApplyExtractionRequest.model_validate(
            {
                "items": [{"item_type": "new_entity", "name": "Anna"}],
                "chapter_id": str(chapter_id),
            },
        )
        assert request.chapter_id == chapter_id

    def test_validator_admits_reserved_keys(self) -> None:
        metadata: dict[str, object] = {
            "role": "hero",
            "provenance": dict(PROVENANCE_V1),
            "resolution": {"merged_into": uuid4()},
        }
        validate_entry_metadata("character", metadata)

    @pytest.mark.asyncio
    async def test_position_resolution_uses_repository(self) -> None:
        from narrare.kb._extraction_position import resolve_chapter_position

        repo = _FakeChapterRepo()
        chapter_id = uuid4()
        repo.seed(chapter_id, position=5)

        position = await resolve_chapter_position(cast("Any", repo), uuid4(), chapter_id)

        assert position == 5
        assert repo.calls == [chapter_id]

    @pytest.mark.asyncio
    async def test_position_resolution_without_chapter_id_skips_lookup(self) -> None:
        from narrare.kb._extraction_position import resolve_chapter_position

        repo = _FakeChapterRepo()

        position = await resolve_chapter_position(cast("Any", repo), uuid4(), None)

        assert position is None
        assert repo.calls == []

    @pytest.mark.asyncio
    async def test_position_resolution_unknown_chapter_yields_none(self) -> None:
        from narrare.kb._extraction_position import resolve_chapter_position

        repo = _FakeChapterRepo()

        position = await resolve_chapter_position(cast("Any", repo), uuid4(), uuid4())

        assert position is None
