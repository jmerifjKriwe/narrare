"""Unit tests for the deterministic merge executor (ADR-085 P4, spec §6).

Pins the seven §6 semantics: deterministic survivor order (fact keys →
relationships → longer name → older ``created_at``), recursive two-sided
metadata merge with scalar conflicts recorded — never dropped, relationship
re-pointing with ``uq_kb_relationships_unique`` collision skips (counterpart
edges never deleted), loser deprecation + ``resolution`` metadata without
deletion, survivor ``embeddings_dirty``, single-savepoint execution with
idempotent re-execution, and the OQ-5 ``result_name`` ruling (custom names
rejected; only the ``decide_rename`` auto-result is accepted).

Fakes, builders, and the executor wiring live in ``_merge_helpers.py``
(RULE-04).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from narrare.kb.entity_resolution.merge_executor import select_survivor
from narrare.kb.entity_resolution.schemas_resolution import MergeExecutionResult, MergePlan
from narrare_core.shared.errors import NotFoundError

from ._merge_helpers import NOVEL, SUGGESTION_ID, USER, _FakeEntry, _world

# --- §6.1 Deterministic survivor order ------------------------------------------


class TestSelectSurvivor:
    def test_more_metadata_fact_keys_win(self) -> None:
        rich = _FakeEntry(name="Anna", metadata={"age": 24, "job": "smith"})
        poor = _FakeEntry(name="Anna", metadata={"age": 24})
        assert select_survivor(rich, poor, {}) == rich.id

    def test_more_relationships_break_fact_key_tie(self) -> None:
        a = _FakeEntry(name="Anna", metadata={"age": 24})
        b = _FakeEntry(name="Anna", metadata={"job": "smith"})
        assert select_survivor(a, b, {a.id: 1, b.id: 2}) == b.id

    def test_longer_name_breaks_relationship_tie(self) -> None:
        short = _FakeEntry(name="Anna")
        full = _FakeEntry(name="Anna Meyer")
        assert select_survivor(short, full, {short.id: 1, full.id: 1}) == full.id

    def test_older_created_at_breaks_name_tie(self) -> None:
        older = _FakeEntry(name="Anne", created_at=datetime.now(tz=UTC) - timedelta(days=1))
        newer = _FakeEntry(name="Anne", created_at=datetime.now(tz=UTC))
        assert select_survivor(older, newer, {}) == older.id


# --- §6.2 Metadata merge ---------------------------------------------------------


class TestMetadataMerge:
    async def test_loser_facts_merge_recursively_without_clobber(self) -> None:
        w = _world(
            survivor=_FakeEntry(
                name="Anna Meyer",
                metadata={"residence": {"city": "Berlin"}, "tags": ["main"]},
            ),
            loser=_FakeEntry(
                name="Anna",
                metadata={
                    "residence": {"district": "Mitte"},
                    "tags": ["main", "hero"],
                    "job": "smith",
                },
            ),
        )
        result = await w.executor.execute(NOVEL, USER, w.plan())
        assert w.survivor.metadata_["residence"] == {"city": "Berlin", "district": "Mitte"}
        assert w.survivor.metadata_["tags"] == ["main", "hero"]
        assert w.survivor.metadata_["job"] == "smith"
        assert "job" in result.merged_fact_keys
        assert result.conflicts == []

    async def test_scalar_conflict_survivor_wins_and_is_recorded(self) -> None:
        w = _world(
            survivor=_FakeEntry(name="Anna Meyer", metadata={"gender": "female"}),
            loser=_FakeEntry(name="Anna", metadata={"gender": "other"}),
        )
        result = await w.executor.execute(NOVEL, USER, w.plan())
        assert w.survivor.metadata_["gender"] == "female"
        assert [(c.key, c.survivor_value, c.loser_value) for c in result.conflicts] == [
            ("gender", "female", "other")
        ]
        resolution = cast("dict[str, object]", w.survivor.metadata_["resolution"])
        assert resolution["conflicts"] == [
            {"key": "gender", "survivor_value": "female", "loser_value": "other"},
        ]
        assert "gender" not in result.merged_fact_keys

    async def test_loser_reserved_keys_never_leak_into_survivor(self) -> None:
        w = _world(
            loser=_FakeEntry(
                name="Anna",
                metadata={
                    "provenance": {"chapters": [1]},
                    "resolution": {"merged_into": "x"},
                    "job": "smith",
                },
            ),
        )
        with capture_logs() as logs:
            result = await w.executor.execute(NOVEL, USER, w.plan())
        assert "provenance" not in w.survivor.metadata_
        resolution = cast("dict[str, object]", w.survivor.metadata_["resolution"])
        assert resolution["conflicts"] == []
        assert resolution["merged_into"] == str(w.survivor.id)
        assert w.survivor.metadata_["job"] == "smith"
        assert "provenance" not in result.merged_fact_keys
        assert any(e["event"] == "merge_reserved_key_skipped" for e in logs)


# --- §6.3 Relationship re-pointing -----------------------------------------------


class TestRelationshipRepoint:
    async def test_edges_on_both_sides_repoint_and_count(self) -> None:
        other = uuid4()
        w = _world()
        out_edge = w.rel_repo.add_edge(source_id=w.loser.id, target_id=other)
        in_edge = w.rel_repo.add_edge(source_id=other, target_id=w.loser.id)
        result = await w.executor.execute(NOVEL, USER, w.plan())
        assert result.repointed_relationships == 2
        assert result.skipped_relationships == 0
        assert (out_edge.source_id, out_edge.target_id) == (w.survivor.id, other)
        assert (in_edge.source_id, in_edge.target_id) == (other, w.survivor.id)
        assert len(w.rel_repo.updates) == 2

    async def test_colliding_edge_is_skipped_and_counted_counterpart_kept(self) -> None:
        other = uuid4()
        w = _world()
        w.rel_repo.add_edge(source_id=w.survivor.id, target_id=other, rel_type="ally")
        colliding = w.rel_repo.add_edge(source_id=w.loser.id, target_id=other, rel_type="ally")
        result = await w.executor.execute(NOVEL, USER, w.plan())
        assert result.skipped_relationships == 1
        assert result.repointed_relationships == 0
        assert colliding.source_id == w.loser.id
        assert w.rel_repo.updates == []

    async def test_loser_to_survivor_edge_skips_as_self_reference(self) -> None:
        w = _world()
        w.rel_repo.add_edge(source_id=w.loser.id, target_id=w.survivor.id)
        result = await w.executor.execute(NOVEL, USER, w.plan())
        assert result.skipped_relationships == 1
        assert result.repointed_relationships == 0


# --- §6.4/§6.5 Loser + survivor end state ----------------------------------------


class TestLoserAndSurvivorState:
    async def test_loser_deprecated_with_resolution_metadata_and_never_deleted(self) -> None:
        w = _world()
        await w.executor.execute(NOVEL, USER, w.plan(confidence=0.91))
        assert w.loser.status == "deprecated"
        assert w.kb_repo.entries[w.loser.id] is w.loser
        block = cast("dict[str, object]", w.loser.metadata_["resolution"])
        assert block["merged_into"] == str(w.survivor.id)
        assert block["suggestion_id"] == SUGGESTION_ID
        assert block["confidence"] == 0.91
        assert datetime.fromisoformat(str(block["merged_at"])) is not None

    async def test_survivor_gets_embeddings_dirty_and_keeps_fuller_name(self) -> None:
        w = _world()  # survivor "Anna Meyer" ← loser "Anna": downgrade guard keeps name
        await w.executor.execute(NOVEL, USER, w.plan())
        assert w.survivor.embeddings_dirty is True
        assert w.survivor.name == "Anna Meyer"

    async def test_canonical_name_pick_via_decide_rename(self) -> None:
        w = _world(
            survivor=_FakeEntry(name="Anna"),
            loser=_FakeEntry(name="Anna Meyer"),
        )
        await w.executor.execute(NOVEL, USER, w.plan())
        assert w.survivor.name == "Anna Meyer"
        assert w.loser.name == "Anna Meyer"  # loser row keeps its own name


# --- OQ-5 result_name ruling ------------------------------------------------------


class TestResultNameRuling:
    async def test_result_name_matching_auto_result_is_accepted(self) -> None:
        w = _world(
            survivor=_FakeEntry(name="Anna"),
            loser=_FakeEntry(name="Anna Meyer"),
        )
        await w.executor.execute(NOVEL, USER, w.plan(result_name="Anna Meyer"))
        assert w.survivor.name == "Anna Meyer"

    async def test_custom_result_name_is_rejected_before_any_write(self) -> None:
        w = _world(
            survivor=_FakeEntry(name="Anna"),
            loser=_FakeEntry(name="Anna Meyer"),
        )
        with pytest.raises(ValueError, match="OQ-5"):
            await w.executor.execute(NOVEL, USER, w.plan(result_name="Anna Maria Meyer"))
        assert w.survivor.name == "Anna"
        assert w.kb_repo.updates == []
        assert w.session.begun == 0


# --- Fix round 1: canonical-name ruling (longer name wins, §6.1 intent) -----------


class TestCanonicalNameRuling:
    async def test_disjoint_shorter_loser_name_does_not_rename_survivor(self) -> None:
        w = _world(survivor=_FakeEntry(name="Anna Meyer"), loser=_FakeEntry(name="Bea"))
        await w.executor.execute(NOVEL, USER, w.plan())
        assert w.survivor.name == "Anna Meyer"

    async def test_disjoint_longer_loser_name_becomes_canonical(self) -> None:
        w = _world(survivor=_FakeEntry(name="Bea"), loser=_FakeEntry(name="Konstanze"))
        await w.executor.execute(NOVEL, USER, w.plan())
        assert w.survivor.name == "Konstanze"

    async def test_equal_length_names_keep_survivor_name(self) -> None:
        w = _world(survivor=_FakeEntry(name="Anne"), loser=_FakeEntry(name="Lena"))
        await w.executor.execute(NOVEL, USER, w.plan())
        assert w.survivor.name == "Anne"


# --- Fix round 1: chained-merge conflict accumulation ------------------------------


class TestChainedMerge:
    async def test_prior_survivor_conflicts_are_preserved_and_appended(self) -> None:
        prior_conflict = {
            "key": "eye_color",
            "survivor_value": "green",
            "loser_value": "blue",
        }
        w = _world(
            survivor=_FakeEntry(
                name="Anna Meyer",
                metadata={
                    "gender": "female",
                    "resolution": {
                        "conflicts": [prior_conflict],
                        "merged_into": "00000000-0000-0000-0000-000000000001",
                    },
                },
            ),
            loser=_FakeEntry(name="Anna", metadata={"gender": "other"}),
        )
        result = await w.executor.execute(NOVEL, USER, w.plan())
        resolution = cast("dict[str, object]", w.survivor.metadata_["resolution"])
        assert resolution["conflicts"] == [
            prior_conflict,
            {"key": "gender", "survivor_value": "female", "loser_value": "other"},
        ]
        assert resolution["merged_into"] == str(w.survivor.id)
        assert resolution["suggestion_id"] == SUGGESTION_ID
        assert [c.key for c in result.conflicts] == ["gender"]


# --- §6.6 Idempotency -------------------------------------------------------------


class TestIdempotency:
    async def test_second_execution_on_deprecated_loser_is_logged_noop(self) -> None:
        w = _world()
        first = await w.executor.execute(NOVEL, USER, w.plan())
        writes_after_first = len(w.kb_repo.updates) + len(w.rel_repo.updates)
        with capture_logs() as logs:
            second = await w.executor.execute(NOVEL, USER, w.plan())
        assert second == MergeExecutionResult(
            survivor_id=w.survivor.id,
            loser_id=w.loser.id,
            merged_fact_keys=[],
            repointed_relationships=0,
            skipped_relationships=0,
            conflicts=[],
        )
        assert first.survivor_id == w.survivor.id
        assert len(w.kb_repo.updates) + len(w.rel_repo.updates) == writes_after_first
        assert any(e["event"] == "merge_already_applied" for e in logs)

    async def test_replay_returns_the_persisted_original_counts(self) -> None:
        other = uuid4()
        w = _world(loser=_FakeEntry(name="Anna", metadata={"job": "smith"}))
        w.rel_repo.add_edge(source_id=w.loser.id, target_id=other)
        first = await w.executor.execute(NOVEL, USER, w.plan())
        second = await w.executor.execute(NOVEL, USER, w.plan())
        assert first.merged_fact_keys == second.merged_fact_keys == ["job"]
        assert first.repointed_relationships == second.repointed_relationships == 1
        assert first.skipped_relationships == second.skipped_relationships == 0

    async def test_stale_plan_with_wrong_survivor_is_rejected(self) -> None:
        w = _world()
        third = _FakeEntry(name="Third Party")
        w.kb_repo.seed(third)
        await w.executor.execute(NOVEL, USER, w.plan())
        stale = MergePlan(
            survivor_id=third.id,
            loser_id=w.loser.id,
            suggestion_id=SUGGESTION_ID,
        )
        with pytest.raises(ValueError, match="stale"):
            await w.executor.execute(NOVEL, USER, stale)


# --- Plan validation ---------------------------------------------------------------


class TestPlanValidation:
    async def test_identical_survivor_and_loser_is_rejected(self) -> None:
        w = _world()
        plan = MergePlan(
            survivor_id=w.survivor.id, loser_id=w.survivor.id, suggestion_id=SUGGESTION_ID
        )
        with pytest.raises(ValueError, match="differ"):
            await w.executor.execute(NOVEL, USER, plan)

    async def test_missing_entry_raises_not_found(self) -> None:
        w = _world()
        plan = MergePlan(survivor_id=uuid4(), loser_id=w.loser.id, suggestion_id=SUGGESTION_ID)
        with pytest.raises(NotFoundError):
            await w.executor.execute(NOVEL, USER, plan)

    async def test_foreign_novel_entry_raises_not_found(self) -> None:
        w = _world(loser=_FakeEntry(name="Anna", novel_id=uuid4()))
        with pytest.raises(NotFoundError):
            await w.executor.execute(NOVEL, USER, w.plan())

    async def test_deprecated_survivor_is_rejected(self) -> None:
        w = _world(survivor=_FakeEntry(name="Anna Meyer", status="deprecated"))
        with pytest.raises(ValueError, match="deprecated"):
            await w.executor.execute(NOVEL, USER, w.plan())


# --- §6.6 Transaction ---------------------------------------------------------------


class TestTransaction:
    async def test_merge_runs_inside_exactly_one_savepoint(self) -> None:
        w = _world()
        await w.executor.execute(NOVEL, USER, w.plan())
        assert w.session.begun == 1
        assert w.session.rollbacks == 0

    async def test_failure_rolls_back_savepoint_and_propagates(self) -> None:
        w = _world()
        w.rel_repo.fail_next_update = True
        w.rel_repo.add_edge(source_id=w.loser.id, target_id=uuid4())
        with pytest.raises(RuntimeError, match="edge update failed"):
            await w.executor.execute(NOVEL, USER, w.plan())
        assert w.session.rollbacks == 1
        assert w.loser.status != "deprecated"
