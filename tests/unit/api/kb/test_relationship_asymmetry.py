"""Unit tests for RelationshipAsymmetryChecker — algorithmic relationship consistency.

Tests the pure algorithmic asymmetry detection with in-memory fakes.
No LLM calls, no database — just adjacency map + inverse mapping logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from narrare.kb.relationship_asymmetry import RelationshipAsymmetryChecker
from narrare.kb.worldbuilding_contracts import WorldbuildingSeverity

# ---------------------------------------------------------------------------
# Fake relationship object
# ---------------------------------------------------------------------------


@dataclass
class FakeRel:
    """Minimal fake KBRelationship for testing."""

    source_id: UUID
    target_id: UUID
    rel_type: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid4())


def _make_checker(
    *,
    adjacency: dict[str, set[str]] | None = None,
    rels_by_entry: dict[str, list[FakeRel]] | None = None,
    inverse_map: dict[str, str | None] | None = None,
) -> tuple[RelationshipAsymmetryChecker, dict[str, AsyncMock | MagicMock]]:
    """Create checker with mocked dependencies.

    Args:
        adjacency: entity_id → set of connected entity_ids.
        rels_by_entry: entity_id → list of FakeRel for outgoing direction.
        inverse_map: rel_type → expected inverse type.

    Returns:
        (checker, mocks_dict) for assertion access.
    """
    _adjacency = adjacency or {}
    _rels = rels_by_entry or {}
    _inverse = inverse_map or {"mentor": "mentee", "ally": "ally"}

    repo = AsyncMock()
    repo.get_adjacency_map = AsyncMock(return_value=_adjacency)
    repo.list_for_entry = AsyncMock(
        side_effect=lambda entry_id, direction="outgoing": _rels.get(str(entry_id), []),
    )

    service = MagicMock(spec=["get_inverse_suggestion"])
    service.get_inverse_suggestion = MagicMock(
        spec=["__call__"],
        side_effect=lambda rt: _inverse.get(rt),
    )

    checker = RelationshipAsymmetryChecker(rel_repo=repo, rel_service=service)
    return checker, {"repo": repo, "service": service}


# ---------------------------------------------------------------------------
# Tests: asymmetry detection
# ---------------------------------------------------------------------------


class TestNoAsymmetryWhenInverseMatches:
    """When A→B 'mentor' and B→A 'mentee' exist, no issues are reported."""

    async def test_no_asymmetry_when_inverse_matches(self) -> None:
        """Symmetric pair with correct inverse types produces no issues."""
        a_id = _uuid()
        b_id = _uuid()

        checker, _mocks = _make_checker(
            adjacency={a_id: {b_id}},
            rels_by_entry={
                a_id: [FakeRel(source_id=UUID(a_id), target_id=UUID(b_id), rel_type="mentor")],
                b_id: [FakeRel(source_id=UUID(b_id), target_id=UUID(a_id), rel_type="mentee")],
            },
            inverse_map={"mentor": "mentee"},
        )

        issues = await checker.check(novel_id=uuid4())

        assert issues == []


class TestAsymmetryDetectedWhenReverseMissing:
    """When A→B 'mentor' exists but B→A is absent, an INFO issue is reported."""

    async def test_asymmetry_detected_when_reverse_missing(self) -> None:
        """Missing reverse relationship produces an INFO-severity issue."""
        a_id = _uuid()
        b_id = _uuid()

        checker, _mocks = _make_checker(
            adjacency={a_id: {b_id}},
            rels_by_entry={
                a_id: [FakeRel(source_id=UUID(a_id), target_id=UUID(b_id), rel_type="mentor")],
                b_id: [],
            },
            inverse_map={"mentor": "mentee"},
        )

        issues = await checker.check(novel_id=uuid4())

        assert len(issues) == 1
        issue = issues[0]
        assert issue.source_id == a_id
        assert issue.target_id == b_id
        assert issue.forward_rel_type == "mentor"
        assert issue.reverse_rel_type is None
        assert issue.expected_inverse == "mentee"
        assert issue.severity == WorldbuildingSeverity.INFO


class TestAsymmetryDetectedWhenWrongReverseType:
    """When A→B 'mentor' and B→A 'rival' (not 'mentee'), a MINOR issue is reported."""

    async def test_asymmetry_detected_when_wrong_reverse_type(self) -> None:
        """Reverse relationship with wrong type produces a MINOR-severity issue."""
        a_id = _uuid()
        b_id = _uuid()

        checker, _mocks = _make_checker(
            adjacency={a_id: {b_id}},
            rels_by_entry={
                a_id: [FakeRel(source_id=UUID(a_id), target_id=UUID(b_id), rel_type="mentor")],
                b_id: [FakeRel(source_id=UUID(b_id), target_id=UUID(a_id), rel_type="rival")],
            },
            inverse_map={"mentor": "mentee"},
        )

        issues = await checker.check(novel_id=uuid4())

        assert len(issues) == 1
        issue = issues[0]
        assert issue.source_id == a_id
        assert issue.target_id == b_id
        assert issue.forward_rel_type == "mentor"
        assert issue.reverse_rel_type == "rival"
        assert issue.expected_inverse == "mentee"
        assert issue.severity == WorldbuildingSeverity.MINOR


class TestNoAsymmetryWhenNoInverseExpected:
    """When rel_type has no inverse mapping, the pair is skipped entirely."""

    async def test_no_asymmetry_when_no_inverse_expected(self) -> None:
        """Relationship type without an inverse suggestion produces no issues."""
        a_id = _uuid()
        b_id = _uuid()

        checker, _mocks = _make_checker(
            adjacency={a_id: {b_id}},
            rels_by_entry={
                a_id: [FakeRel(source_id=UUID(a_id), target_id=UUID(b_id), rel_type="custom_type")],
                b_id: [],
            },
            inverse_map={"mentor": "mentee"},  # no entry for "custom_type"
        )

        issues = await checker.check(novel_id=uuid4())

        assert issues == []


class TestPairsNotDoubleCounted:
    """frozenset deduplication ensures each pair is checked exactly once."""

    async def test_pairs_not_double_counted(self) -> None:
        """When adjacency has A→B and B→A, only one issue is produced."""
        a_id = _uuid()
        b_id = _uuid()

        checker, _mocks = _make_checker(
            adjacency={a_id: {b_id}, b_id: {a_id}},
            rels_by_entry={
                a_id: [FakeRel(source_id=UUID(a_id), target_id=UUID(b_id), rel_type="mentor")],
                b_id: [],
            },
            inverse_map={"mentor": "mentee"},
        )

        issues = await checker.check(novel_id=uuid4())

        # Only 1 issue despite both directions appearing in adjacency
        assert len(issues) == 1
        issue = issues[0]
        assert issue.forward_rel_type == "mentor"
        assert issue.severity == WorldbuildingSeverity.INFO
