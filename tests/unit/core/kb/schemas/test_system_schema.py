"""Tests for kb/schemas/system.py — SystemMetadata schema validation.

Covers:
1. Flat fields (backward compat)
2. Nested group models: SystemMechanics, SystemPractitioners, SystemOrigins
3. Extra fields preserved
4. Empty metadata passes validation
"""

from __future__ import annotations

from narrare_core.kb.schemas.system import (
    SystemMechanics,
    SystemMetadata,
    SystemOrigins,
    SystemPractitioners,
)


class TestSystemMechanics:
    """SystemMechanics nested group model."""

    def test_all_optional(self) -> None:
        m = SystemMechanics()
        assert m.rules is None
        assert m.cost is None
        assert m.limitations is None
        assert m.levels is None

    def test_with_data(self) -> None:
        m = SystemMechanics(
            rules=["Requires incantation", "Drains stamina"],
            cost="Life force",
            limitations=["Cannot raise the dead"],
            levels=["Apprentice", "Adept", "Master"],
        )
        assert len(m.rules or []) == 2
        assert len(m.levels or []) == 3

    def test_extra_fields_preserved(self) -> None:
        m = SystemMechanics(rules=["Test"], cooldown="10 seconds")  # type: ignore[call-arg]
        assert m.cooldown == "10 seconds"  # type: ignore[attr-defined]


class TestSystemPractitioners:
    """SystemPractitioners nested group model."""

    def test_all_optional(self) -> None:
        p = SystemPractitioners()
        assert p.users is None

    def test_with_data(self) -> None:
        p = SystemPractitioners(
            users=["Mage Guild"],
            requirements="Born with the gift",
            training="10 years of study",
            organizations=["Academy of Magic"],
        )
        assert p.requirements == "Born with the gift"


class TestSystemOrigins:
    """SystemOrigins nested group model."""

    def test_all_optional(self) -> None:
        o = SystemOrigins()
        assert o.source is None

    def test_with_data(self) -> None:
        o = SystemOrigins(
            source="Divine gift",
            discovered_by="First Mage",
            discovered_date="Year 0",
            history="Passed down through generations",
        )
        assert o.source == "Divine gift"


class TestSystemMetadata:
    """SystemMetadata with flat and nested fields."""

    def test_flat_fields_only(self) -> None:
        meta = SystemMetadata(
            system_type="magic",
            practitioners=["Wizards", "Sorcerers"],
        )
        assert meta.system_type == "magic"
        assert len(meta.practitioners or []) == 2

    def test_with_nested_groups(self) -> None:
        meta = SystemMetadata(
            system_type="technology",
            mechanics=SystemMechanics(rules=["Needs power source"]),
            practitioner_details=SystemPractitioners(users=["Engineers"]),
            origins=SystemOrigins(source="Alien technology"),
        )
        assert meta.mechanics is not None
        assert meta.practitioner_details is not None
        assert meta.origins is not None

    def test_nested_groups_optional(self) -> None:
        meta = SystemMetadata()
        assert meta.mechanics is None
        assert meta.practitioner_details is None
        assert meta.origins is None

    def test_extra_fields_preserved(self) -> None:
        meta = SystemMetadata(custom_energy="mana")  # type: ignore[call-arg]
        assert meta.custom_energy == "mana"  # type: ignore[attr-defined]

    def test_empty_metadata(self) -> None:
        meta = SystemMetadata()
        assert meta.system_type is None

    def test_serialization_roundtrip(self) -> None:
        meta = SystemMetadata(
            system_type="psionics",
            mechanics=SystemMechanics(cost="Mental energy"),
        )
        data = meta.model_dump()
        restored = SystemMetadata.model_validate(data)
        assert restored.system_type == "psionics"
        assert restored.mechanics is not None
