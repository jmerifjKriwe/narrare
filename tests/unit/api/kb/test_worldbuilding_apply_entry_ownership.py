"""W2 — worldbuilding apply_connections entry∈novel regression tests (service).

Before W2 the novel gate (S8) on ``WorldbuildingService.apply_connections``
was followed only by a duplicate check: the client-roundtripped analysis
payload carried arbitrary entity ids, so a novel OWNER could attach
foreign-novel entries to relationships — polluting the victim's graph
view / relationship-existence oracle (data-integrity sibling of IDOR).

The fix follows the S10 shape (``RelationshipService.create``): every
referenced entry id must belong to the gated novel, checked in ONE batch
ownership query before any duplicate check or write. A single
foreign/unknown id rejects the whole batch (no partial writes); foreign ≡
unknown (anti-enumeration), both ``NotFoundError`` → 404.

The novel-gate matrix (S8) lives in ``test_improve_worldbuilding_ownership.py``
(RULE-04 split); the HTTP-level matrix in
``test_improve_worldbuilding_ownership_api.py``.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare.kb.worldbuilding_contracts import (
    ConnectionSuggestion,
    WorldbuildingApplyRequest,
)
from narrare_core.shared.errors import NotFoundError

from ._test_fakes_improve_worldbuilding import (
    FakeKBEntry,
    make_worldbuilding_analysis,
    make_worldbuilding_ownership_service,
)

USER_A = uuid4()  # rightful owner of NOVEL_ID (the victim)
USER_B = uuid4()  # owner of FOREIGN_NOVEL_ID

NOVEL_ID = uuid4()  # owned by USER_A
FOREIGN_NOVEL_ID = uuid4()  # a real novel — just not the caller's

_OWNERSHIP = {NOVEL_ID: USER_A, FOREIGN_NOVEL_ID: USER_B}

ALICE_ID = uuid4()  # victim's entry inside NOVEL_ID
BOB_ID = uuid4()  # victim's entry inside NOVEL_ID
CAROL_ID = uuid4()  # foreign entry inside FOREIGN_NOVEL_ID
DAVE_ID = uuid4()  # victim's entry inside NOVEL_ID
ERIN_ID = uuid4()  # victim's entry inside NOVEL_ID


def _wb_entries() -> dict[UUID, FakeKBEntry]:
    """The victim's entries plus one foreign entry (W2 matrix fixture)."""
    return {
        ALICE_ID: FakeKBEntry(id=ALICE_ID, novel_id=NOVEL_ID, name="Alice"),
        BOB_ID: FakeKBEntry(id=BOB_ID, novel_id=NOVEL_ID, name="Bob"),
        CAROL_ID: FakeKBEntry(id=CAROL_ID, novel_id=FOREIGN_NOVEL_ID, name="Carol"),
        DAVE_ID: FakeKBEntry(id=DAVE_ID, novel_id=NOVEL_ID, name="Dave"),
        ERIN_ID: FakeKBEntry(id=ERIN_ID, novel_id=NOVEL_ID, name="Erin"),
    }


def _wb_suggestion(
    idx: int,
    source_id: UUID,
    target_id: UUID,
    *,
    source_name: str = "Alice",
    target_name: str = "Bob",
) -> ConnectionSuggestion:
    """A connection suggestion with explicit (attacker-choosable) entity ids."""
    return ConnectionSuggestion(
        finding_index=idx,
        source_entity_id=str(source_id),
        source_entity_name=source_name,
        source_entity_type="character",
        target_entity_id=str(target_id),
        target_entity_name=target_name,
        target_entity_type="character",
        suggested_rel_type="ally",
        reasoning="Characters interact frequently",
        confidence=0.85,
        story_relevance=0.7,
    )


class TestWorldbuildingApplyEntryOwnership:
    """``apply_connections`` validates entries∈novel before ANY write."""

    async def test_owner_apply_with_all_entries_in_novel_succeeds(self) -> None:
        """Matrix case (1): owner's happy path unchanged, one batch check."""
        service, _, rel_repo, cache, kb_repo, _ = make_worldbuilding_ownership_service(
            _OWNERSHIP, _wb_entries()
        )
        analysis = make_worldbuilding_analysis(NOVEL_ID, [_wb_suggestion(0, ALICE_ID, BOB_ID)])

        result = await service.apply_connections(
            novel_id=NOVEL_ID,
            user_id=USER_A,
            request=WorldbuildingApplyRequest(finding_indices=[0]),
            analysis=analysis,
        )

        assert result.success is True
        assert result.created_count == 1
        assert len(rel_repo.created) == 1
        assert cache.delete_all_calls == [str(NOVEL_ID)]
        assert kb_repo.filter_ids_in_novel_calls == [(NOVEL_ID, {ALICE_ID, BOB_ID})]

    async def test_apply_with_foreign_entry_raises_not_found_no_writes(self) -> None:
        """Foreign entry id → 404 BEFORE any duplicate check or write."""
        service, _, rel_repo, cache, _, _ = make_worldbuilding_ownership_service(
            _OWNERSHIP, _wb_entries()
        )
        analysis = make_worldbuilding_analysis(
            NOVEL_ID, [_wb_suggestion(0, ALICE_ID, CAROL_ID, target_name="Carol")]
        )

        with pytest.raises(NotFoundError, match="KBEntry") as exc_info:
            await service.apply_connections(
                novel_id=NOVEL_ID,
                user_id=USER_A,
                request=WorldbuildingApplyRequest(finding_indices=[0]),
                analysis=analysis,
            )

        assert str(exc_info.value) == f"KBEntry ({CAROL_ID}) not found"
        assert rel_repo.exists_calls == []
        assert rel_repo.created == []
        assert cache.delete_all_calls == []

    async def test_apply_mixed_batch_rejected_whole_no_partial_writes(self) -> None:
        """One foreign id in the batch rejects EVERYTHING — the valid
        suggestion is not probed or written (no partial writes)."""
        service, _, rel_repo, _, _, _ = make_worldbuilding_ownership_service(
            _OWNERSHIP, _wb_entries()
        )
        analysis = make_worldbuilding_analysis(
            NOVEL_ID,
            [
                _wb_suggestion(0, ALICE_ID, BOB_ID),
                _wb_suggestion(1, ALICE_ID, CAROL_ID, target_name="Carol"),
            ],
        )

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.apply_connections(
                novel_id=NOVEL_ID,
                user_id=USER_A,
                request=WorldbuildingApplyRequest(finding_indices=[0, 1]),
                analysis=analysis,
            )

        assert rel_repo.exists_calls == []
        assert rel_repo.created == []

    async def test_apply_unknown_entry_indistinguishable_from_foreign(self) -> None:
        """Unknown entry ≡ foreign entry — identical error shape (S10 shape)."""
        service, _, _, _, _, _ = make_worldbuilding_ownership_service(_OWNERSHIP, _wb_entries())
        unknown_entry_id = uuid4()
        foreign_analysis = make_worldbuilding_analysis(
            NOVEL_ID, [_wb_suggestion(0, ALICE_ID, CAROL_ID, target_name="Carol")]
        )
        unknown_analysis = make_worldbuilding_analysis(
            NOVEL_ID, [_wb_suggestion(0, ALICE_ID, unknown_entry_id, target_name="Ghost")]
        )

        with pytest.raises(NotFoundError) as foreign_exc:
            await service.apply_connections(
                novel_id=NOVEL_ID,
                user_id=USER_A,
                request=WorldbuildingApplyRequest(finding_indices=[0]),
                analysis=foreign_analysis,
            )
        with pytest.raises(NotFoundError) as unknown_exc:
            await service.apply_connections(
                novel_id=NOVEL_ID,
                user_id=USER_A,
                request=WorldbuildingApplyRequest(finding_indices=[0]),
                analysis=unknown_analysis,
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"KBEntry ({CAROL_ID}) not found"
        assert str(unknown_exc.value) == f"KBEntry ({unknown_entry_id}) not found"

    async def test_apply_batch_ownership_single_query_not_n_plus_one(self) -> None:
        """N suggestions x 2 ids → exactly ONE batch ownership query with
        the full id set (the N+1 per-entry lookup shape is a regression)."""
        service, _, _rel_repo, _, kb_repo, _ = make_worldbuilding_ownership_service(
            _OWNERSHIP, _wb_entries()
        )
        analysis = make_worldbuilding_analysis(
            NOVEL_ID,
            [
                _wb_suggestion(0, ALICE_ID, BOB_ID),
                _wb_suggestion(1, DAVE_ID, ERIN_ID, source_name="Dave", target_name="Erin"),
            ],
        )

        result = await service.apply_connections(
            novel_id=NOVEL_ID,
            user_id=USER_A,
            request=WorldbuildingApplyRequest(finding_indices=[0, 1]),
            analysis=analysis,
        )

        assert result.success is True
        assert result.created_count == 2
        assert kb_repo.get_by_id_calls == []  # no per-entry fallback lookups
        assert kb_repo.filter_ids_in_novel_calls == [
            (NOVEL_ID, {ALICE_ID, BOB_ID, DAVE_ID, ERIN_ID})
        ]

    async def test_apply_unselected_foreign_suggestion_ignored(self) -> None:
        """Only ids about to be WRITTEN are validated: a foreign id sitting
        in an unselected suggestion is harmless and must not reject the batch."""
        service, _, _rel_repo, _, _, _ = make_worldbuilding_ownership_service(
            _OWNERSHIP, _wb_entries()
        )
        analysis = make_worldbuilding_analysis(
            NOVEL_ID,
            [
                _wb_suggestion(0, ALICE_ID, BOB_ID),
                _wb_suggestion(1, ALICE_ID, CAROL_ID, target_name="Carol"),
            ],
        )

        result = await service.apply_connections(
            novel_id=NOVEL_ID,
            user_id=USER_A,
            request=WorldbuildingApplyRequest(finding_indices=[0]),
            analysis=analysis,
        )

        assert result.success is True
        assert result.created_count == 1

    async def test_apply_malformed_entity_id_keeps_per_item_error(self) -> None:
        """Malformed uuid strings keep the per-item error response (200
        success=False) — pre-validation must not 500 on garbage ids."""
        service, _, _, _, _, _ = make_worldbuilding_ownership_service(_OWNERSHIP, _wb_entries())
        broken = _wb_suggestion(0, ALICE_ID, BOB_ID)
        broken = broken.model_copy(update={"source_entity_id": "not-a-uuid"})
        analysis = make_worldbuilding_analysis(NOVEL_ID, [broken])

        result = await service.apply_connections(
            novel_id=NOVEL_ID,
            user_id=USER_A,
            request=WorldbuildingApplyRequest(finding_indices=[0]),
            analysis=analysis,
        )

        assert result.success is False
        assert result.created_count == 0
        assert result.failed_count == 1
        assert "index 0" in result.errors[0]
