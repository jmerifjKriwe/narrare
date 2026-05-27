"""Tests for kb/schemas/timeline.py — TimelineMetadata schema validation.

Covers:
1. Flat fields (backward compat)
2. Nested group models: TimelinePeriod, TimelineEvents
3. Extra fields preserved
4. Empty metadata passes validation
"""

from __future__ import annotations

from narrare_core.kb.schemas.timeline import (
    TimelineEvents,
    TimelineMetadata,
    TimelinePeriod,
)


class TestTimelinePeriod:
    """TimelinePeriod nested group model."""

    def test_all_optional(self) -> None:
        p = TimelinePeriod()
        assert p.start_date is None
        assert p.end_date is None
        assert p.duration is None
        assert p.era_name is None

    def test_with_data(self) -> None:
        p = TimelinePeriod(
            start_date="1000 AD",
            end_date="1200 AD",
            duration="200 years",
            era_name="The Golden Age",
        )
        assert p.era_name == "The Golden Age"
        assert p.duration == "200 years"

    def test_extra_fields_preserved(self) -> None:
        p = TimelinePeriod(era_name="Test", calendar_system="Lunar")  # type: ignore[call-arg]
        assert p.calendar_system == "Lunar"  # type: ignore[attr-defined]


class TestTimelineEvents:
    """TimelineEvents nested group model."""

    def test_all_optional(self) -> None:
        e = TimelineEvents()
        assert e.major_events is None
        assert e.key_figures is None
        assert e.conflicts is None
        assert e.discoveries is None

    def test_with_data(self) -> None:
        e = TimelineEvents(
            major_events=["The Great Flood", "The Rebellion"],
            key_figures=["Hero A", "Villain B"],
            conflicts=["War of the Roses"],
            discoveries=["Gunpowder"],
        )
        assert len(e.major_events or []) == 2
        assert len(e.key_figures or []) == 2

    def test_extra_fields_preserved(self) -> None:
        e = TimelineEvents(major_events=["Test"], cultural_impact="High")  # type: ignore[call-arg]
        assert e.cultural_impact == "High"  # type: ignore[attr-defined]


class TestTimelineMetadata:
    """TimelineMetadata with flat and nested fields."""

    def test_flat_fields_only(self) -> None:
        meta = TimelineMetadata(
            era="Medieval",
            start_date="500 AD",
            end_date="1500 AD",
        )
        assert meta.era == "Medieval"

    def test_with_nested_groups(self) -> None:
        meta = TimelineMetadata(
            era="Renaissance",
            period=TimelinePeriod(era_name="Italian Renaissance"),
            events=TimelineEvents(major_events=["Invention of printing press"]),
        )
        assert meta.period is not None
        assert meta.period.era_name == "Italian Renaissance"
        assert meta.events is not None

    def test_nested_groups_optional(self) -> None:
        meta = TimelineMetadata()
        assert meta.period is None
        assert meta.events is None

    def test_extra_fields_preserved(self) -> None:
        meta = TimelineMetadata(custom_tag="important")  # type: ignore[call-arg]
        assert meta.custom_tag == "important"  # type: ignore[attr-defined]

    def test_empty_metadata(self) -> None:
        meta = TimelineMetadata()
        assert meta.era is None
        assert meta.start_date is None

    def test_serialization_roundtrip(self) -> None:
        meta = TimelineMetadata(
            era="Prehistoric",
            period=TimelinePeriod(duration="Millions of years"),
            events=TimelineEvents(discoveries=["Fire"]),
        )
        data = meta.model_dump()
        restored = TimelineMetadata.model_validate(data)
        assert restored.era == "Prehistoric"
        assert restored.period is not None
        assert restored.events is not None
