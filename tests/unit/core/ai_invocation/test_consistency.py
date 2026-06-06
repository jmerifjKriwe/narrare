"""Tests for ai_invocation/consistency.py — consistency enums, dataclasses, and Protocol.

Covers:
1. EntityType enum — values, string conversion, membership
2. ConsistencyStatus enum — values, string conversion, membership
3. EntityTypeCheck — construction, frozen=True, defaults
4. KBConsistencyResult — construction, frozen=True, is_consistent property
5. KBConsistencyCheck — Protocol structural typing
"""

from __future__ import annotations

from typing import Protocol as TypingProtocol

import pytest

from narrare_core.ai_invocation.consistency import (
    ConsistencyStatus,
    EntityType,
    EntityTypeCheck,
    KBConsistencyCheck,
    KBConsistencyResult,
)

# ---------------------------------------------------------------------------
# EntityType enum
# ---------------------------------------------------------------------------


class TestEntityType:
    """EntityType enum values, string conversion, membership."""

    def test_values(self) -> None:
        """All expected entity types are defined."""
        values = {e.value for e in EntityType}
        assert values == {"character", "location", "faction", "item", "event"}

    def test_members(self) -> None:
        """All members are accessible by name."""
        assert EntityType.CHARACTER.value == "character"
        assert EntityType.LOCATION.value == "location"
        assert EntityType.FACTION.value == "faction"
        assert EntityType.ITEM.value == "item"
        assert EntityType.EVENT.value == "event"

    def test_str_conversion(self) -> None:
        """StrEnum conversion yields the value string."""
        assert str(EntityType.CHARACTER) == "character"
        assert str(EntityType.LOCATION) == "location"

    def test_membership(self) -> None:
        """String can be tested for membership."""
        assert "character" in {e.value for e in EntityType}
        assert "unknown_type" not in {e.value for e in EntityType}


# ---------------------------------------------------------------------------
# ConsistencyStatus enum
# ---------------------------------------------------------------------------


class TestConsistencyStatus:
    """ConsistencyStatus enum values, string conversion."""

    def test_values(self) -> None:
        """All expected statuses are defined."""
        values = {s.value for s in ConsistencyStatus}
        assert values == {"present", "missing", "stale", "not_applicable"}

    def test_members(self) -> None:
        """All members are accessible by name."""
        assert ConsistencyStatus.PRESENT.value == "present"
        assert ConsistencyStatus.MISSING.value == "missing"
        assert ConsistencyStatus.STALE.value == "stale"
        assert ConsistencyStatus.NOT_APPLICABLE.value == "not_applicable"

    def test_str_conversion(self) -> None:
        """StrEnum conversion yields the value string."""
        assert str(ConsistencyStatus.PRESENT) == "present"
        assert str(ConsistencyStatus.MISSING) == "missing"
        assert str(ConsistencyStatus.STALE) == "stale"
        assert str(ConsistencyStatus.NOT_APPLICABLE) == "not_applicable"

    def test_membership(self) -> None:
        """String can be tested for membership."""
        status_values = {s.value for s in ConsistencyStatus}
        assert "present" in status_values
        assert "unknown_status" not in status_values


# ---------------------------------------------------------------------------
# EntityTypeCheck dataclass
# ---------------------------------------------------------------------------


class TestEntityTypeCheck:
    """EntityTypeCheck dataclass construction, defaults, frozen."""

    def test_construction_with_all_fields(self) -> None:
        """EntityTypeCheck can be constructed with all fields."""
        check = EntityTypeCheck(
            entity_type="character",
            status=ConsistencyStatus.PRESENT,
            count=5,
            detail="5 characters found in KB",
        )
        assert check.entity_type == "character"
        assert check.status == ConsistencyStatus.PRESENT
        assert check.count == 5
        assert check.detail == "5 characters found in KB"

    def test_defaults(self) -> None:
        """EntityTypeCheck uses sensible defaults for optional fields."""
        check = EntityTypeCheck(
            entity_type="location",
            status=ConsistencyStatus.MISSING,
        )
        assert check.entity_type == "location"
        assert check.status == ConsistencyStatus.MISSING
        assert check.count == 0
        assert check.detail == ""

    def test_frozen_cannot_be_modified(self) -> None:
        """EntityTypeCheck is frozen — attribute assignment raises."""
        check = EntityTypeCheck(
            entity_type="faction",
            status=ConsistencyStatus.PRESENT,
        )
        with pytest.raises(AttributeError, match="cannot assign to field"):
            check.entity_type = "item"  # type: ignore[misc]

    def test_frozen_cannot_be_appended(self) -> None:
        """EntityTypeCheck frozen dataclass rejects mutation attempts."""
        check = EntityTypeCheck(
            entity_type="event",
            status=ConsistencyStatus.STALE,
        )
        with pytest.raises(AttributeError, match="cannot assign to field"):
            check.status = ConsistencyStatus.PRESENT  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two EntityTypeCheck instances with same fields are equal."""
        a = EntityTypeCheck(entity_type="item", status=ConsistencyStatus.PRESENT, count=3)
        b = EntityTypeCheck(entity_type="item", status=ConsistencyStatus.PRESENT, count=3)
        assert a == b

    def test_inequality(self) -> None:
        """EntityTypeCheck instances with different fields are not equal."""
        a = EntityTypeCheck(entity_type="item", status=ConsistencyStatus.PRESENT, count=3)
        b = EntityTypeCheck(entity_type="item", status=ConsistencyStatus.MISSING, count=0)
        assert a != b

    def test_repr(self) -> None:
        """EntityTypeCheck has a useful repr."""
        check = EntityTypeCheck(entity_type="character", status=ConsistencyStatus.PRESENT)
        r = repr(check)
        assert "EntityTypeCheck" in r
        assert "character" in r
        assert "present" in r


# ---------------------------------------------------------------------------
# KBConsistencyResult dataclass — is_consistent property
# ---------------------------------------------------------------------------


class TestKBConsistencyResult:
    """KBConsistencyResult construction, frozen, is_consistent property."""

    def test_default_construction(self) -> None:
        """KBConsistencyResult can be constructed with no arguments."""
        result = KBConsistencyResult()
        assert result.entity_type_checks == ()
        assert result.orphan_references == ()
        assert result.freshness_warnings == ()
        assert result.has_all_required_types is False
        assert result.has_orphan_references is False
        assert result.has_stale_profiles is False
        assert result.is_consistent is False

    def test_construction_with_all_fields(self) -> None:
        """KBConsistencyResult can be constructed with all fields."""
        checks = (
            EntityTypeCheck(entity_type="character", status=ConsistencyStatus.PRESENT, count=3),
            EntityTypeCheck(entity_type="location", status=ConsistencyStatus.PRESENT, count=7),
        )
        result = KBConsistencyResult(
            entity_type_checks=checks,
            orphan_references=("loc_unknown_1", "char_orphan_2"),
            freshness_warnings=("char_3 (last updated 2023)",),
            has_all_required_types=True,
            has_orphan_references=True,
            has_stale_profiles=True,
        )
        assert len(result.entity_type_checks) == 2
        assert len(result.orphan_references) == 2
        assert len(result.freshness_warnings) == 1

    def test_is_consistent_all_true(self) -> None:
        """is_consistent is True when all checks pass."""
        result = KBConsistencyResult(
            has_all_required_types=True,
            has_orphan_references=False,
            has_stale_profiles=False,
        )
        assert result.is_consistent is True

    def test_is_consistent_missing_required_types(self) -> None:
        """is_consistent is False when required types are missing."""
        result = KBConsistencyResult(
            has_all_required_types=False,
            has_orphan_references=False,
            has_stale_profiles=False,
        )
        assert result.is_consistent is False

    def test_is_consistent_orphan_references(self) -> None:
        """is_consistent is False when orphan references exist."""
        result = KBConsistencyResult(
            has_all_required_types=True,
            has_orphan_references=True,
            has_stale_profiles=False,
        )
        assert result.is_consistent is False

    def test_is_consistent_stale_profiles(self) -> None:
        """is_consistent is False when stale profiles exist."""
        result = KBConsistencyResult(
            has_all_required_types=True,
            has_orphan_references=False,
            has_stale_profiles=True,
        )
        assert result.is_consistent is False

    def test_is_consistent_multiple_failures(self) -> None:
        """is_consistent is False when multiple failures exist."""
        result = KBConsistencyResult(
            has_all_required_types=False,
            has_orphan_references=True,
            has_stale_profiles=True,
        )
        assert result.is_consistent is False

    def test_is_consistent_all_defaults(self) -> None:
        """is_consistent is False by default (all bools are False)."""
        result = KBConsistencyResult()
        assert result.is_consistent is False

    def test_frozen_cannot_be_modified(self) -> None:
        """KBConsistencyResult is frozen — attribute assignment raises."""
        result = KBConsistencyResult(has_all_required_types=True)
        with pytest.raises(AttributeError, match="cannot assign to field"):
            result.has_all_required_types = False  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two KBConsistencyResult instances with same fields are equal."""
        a = KBConsistencyResult(has_all_required_types=True, has_orphan_references=False)
        b = KBConsistencyResult(has_all_required_types=True, has_orphan_references=False)
        assert a == b

    def test_inequality(self) -> None:
        """KBConsistencyResult instances with different fields are not equal."""
        a = KBConsistencyResult(has_all_required_types=True)
        b = KBConsistencyResult(has_all_required_types=False)
        assert a != b

    def test_repr(self) -> None:
        """KBConsistencyResult has a useful repr."""
        result = KBConsistencyResult(has_all_required_types=True)
        r = repr(result)
        assert "KBConsistencyResult" in r
        assert "has_all_required_types=True" in r


# ---------------------------------------------------------------------------
# KBConsistencyCheck Protocol — structural typing
# ---------------------------------------------------------------------------


class FakeKBConsistencyChecker:
    """Complete KBConsistencyCheck implementation for testing."""

    def __init__(self) -> None:
        self.call_count = 0

    async def check_consistency(
        self,
        project_id: object,
        *,
        required_types: frozenset[str] | None = None,
    ) -> KBConsistencyResult:
        self.call_count += 1
        if required_types is not None:
            return KBConsistencyResult(has_all_required_types=True)
        return KBConsistencyResult(has_all_required_types=True)


class TestKBConsistencyCheckProtocol:
    """KBConsistencyCheck protocol conformance."""

    def test_protocol_is_class(self) -> None:
        """KBConsistencyCheck is a Protocol class, not a function."""
        assert isinstance(KBConsistencyCheck, type)
        assert issubclass(KBConsistencyCheck, TypingProtocol)

    def test_fake_satisfies_protocol(self) -> None:
        """FakeKBConsistencyChecker has the required check_consistency method."""
        fake = FakeKBConsistencyChecker()
        assert hasattr(fake, "check_consistency")
        assert callable(fake.check_consistency)

    @pytest.mark.asyncio
    async def test_fake_returns_consistency_result(self) -> None:
        """FakeKBConsistencyChecker.check_consistency works end-to-end."""
        fake = FakeKBConsistencyChecker()
        result = await fake.check_consistency(project_id="proj_123")
        assert isinstance(result, KBConsistencyResult)
        assert result.has_all_required_types is True
        assert fake.call_count == 1

    @pytest.mark.asyncio
    async def test_fake_with_required_types(self) -> None:
        """FakeKBConsistencyChecker accepts required_types kwarg."""
        fake = FakeKBConsistencyChecker()
        required = frozenset({"character", "location"})
        result = await fake.check_consistency(
            project_id="proj_123",
            required_types=required,
        )
        assert isinstance(result, KBConsistencyResult)
        assert fake.call_count == 1

    @pytest.mark.asyncio
    async def test_fake_with_object_project_id(self) -> None:
        """FakeKBConsistencyChecker accepts arbitrary project_id types."""
        fake = FakeKBConsistencyChecker()
        result = await fake.check_consistency(project_id=42)
        assert isinstance(result, KBConsistencyResult)
        assert fake.call_count == 1

    @pytest.mark.asyncio
    async def test_fake_multiple_calls(self) -> None:
        """FakeKBConsistencyChecker accumulates call count."""
        fake = FakeKBConsistencyChecker()
        await fake.check_consistency(project_id="a")
        await fake.check_consistency(project_id="b")
        await fake.check_consistency(project_id="c")
        assert fake.call_count == 3

    def test_incomplete_does_not_satisfy(self) -> None:
        """Class without check_consistency does not satisfy the protocol."""

        class Incomplete:
            pass

        fake = Incomplete()
        assert not hasattr(fake, "check_consistency") or not callable(
            getattr(fake, "check_consistency", None)
        )
