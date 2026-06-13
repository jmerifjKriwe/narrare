"""Unit tests for timeline envelope enrichment — TimelineEvent → TimelineEventEnvelope.

Tests the enrichment logic including KB entity status cross-referencing.
ADR-044 Slice 3 validation. FIND-009 integration.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from narrare.consistency.timeline_envelope import (
    _build_entity_status_map,
    _split_list_field,
    enrich_timeline_envelopes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_UNSET = object()


def _make_timeline_event(
    event_name: str = "Battle of Thornwall",
    character_refs: list[dict[str, object]] | None = None,
    location_ref: Any = _UNSET,
    causes: str = "",
    consequences: str = "",
    **overrides: Any,
) -> Any:
    """Create a TimelineEvent-like object with sensible defaults.

    Uses SimpleNamespace because _apply_setattr requires real
    SQLAlchemy ORM instances with _sa_instance_state.
    """
    from types import SimpleNamespace

    defaults: dict[str, Any] = {
        "id": uuid4(),
        "novel_id": uuid4(),
        "event_name": event_name,
        "description": "A great battle.",
        "event_type": "plot_point",
        "timestamp_raw": "Day 15, Morning",
        "timestamp_normalized": "day_15_morning",
        "temporal_order": 1,
        "chapter_id": uuid4(),
        "character_refs": character_refs
        if character_refs is not None
        else [
            {"id": str(uuid4()), "name": "Anna"},
            {"id": str(uuid4()), "name": "Kai"},
        ],
        "location_ref": (
            location_ref
            if location_ref is not _UNSET
            else {"id": str(uuid4()), "name": "Thornwall"}
        ),
        "causes": causes,
        "consequences": consequences,
        "source": "narration",
        "confidence": 0.9,
        "is_confirmed": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_kb_entry(name: str = "Anna", status: str = "canon") -> Any:
    """Create a fake KB entry with name and status.

    Uses SimpleNamespace because _apply_setattr requires real
    SQLAlchemy ORM instances with _sa_instance_state.
    """
    from types import SimpleNamespace

    return SimpleNamespace(
        name=name,
        status=status,
        entity_type="character",
        metadata_={},
    )


class FakeKBRepository:
    """Fake KB repository for envelope enrichment tests."""

    def __init__(self, entries: list[Any] | None = None, *, fail: bool = False) -> None:
        self._entries = entries or []
        self._fail = fail

    async def list_entries(
        self,
        novel_id: Any,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        review_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Any], int]:
        """Return seeded entries or raise a configured failure."""
        if self._fail:
            raise RuntimeError("DB down")
        return self._entries, len(self._entries)


def _make_kb_repo(entries: list[Any] | None = None, *, fail: bool = False) -> FakeKBRepository:
    """Create a fake KB repo returning given entries."""
    return FakeKBRepository(entries, fail=fail)


# ---------------------------------------------------------------------------
# Tests — enrich_timeline_envelopes
# ---------------------------------------------------------------------------


class TestEnrichTimelineEnvelopes:
    @pytest.mark.asyncio
    async def test_enriches_single_event(self) -> None:
        """Single event produces one envelope with correct fields."""
        event = _make_timeline_event()
        kb_entries = [_make_kb_entry("Anna", "canon"), _make_kb_entry("Kai", "draft")]
        kb_repo = _make_kb_repo(kb_entries)
        novel_id = uuid4()

        envelopes = await enrich_timeline_envelopes([event], kb_repo, novel_id)

        assert len(envelopes) == 1
        env = envelopes[0]
        assert env.event_name == "Battle of Thornwall"
        assert env.timestamp_raw == "Day 15, Morning"
        assert env.temporal_order == 1
        assert env.is_confirmed is True

    @pytest.mark.asyncio
    async def test_character_refs_enriched_with_status(self) -> None:
        """Character refs include KB status."""
        event = _make_timeline_event(
            character_refs=[
                {"id": "e-1", "name": "Anna"},
                {"id": "e-2", "name": "Unknown Person"},
            ],
        )
        kb_entries = [_make_kb_entry("Anna", "canon")]
        kb_repo = _make_kb_repo(kb_entries)

        envelopes = await enrich_timeline_envelopes([event], kb_repo, uuid4())

        chars = envelopes[0].character_refs
        assert len(chars) == 2
        # Anna is in KB → "active" (canon maps to active)
        anna_ref = next(c for c in chars if c["name"] == "Anna")
        assert anna_ref["status"] == "active"
        # Unknown Person is not in KB → "unknown"
        unknown_ref = next(c for c in chars if c["name"] == "Unknown Person")
        assert unknown_ref["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_location_ref_enriched_with_status(self) -> None:
        """Location ref includes KB status."""
        event = _make_timeline_event(
            location_ref={"id": "l-1", "name": "Thornwall"},
        )
        kb_entries = [_make_kb_entry("Thornwall", "deprecated")]
        kb_repo = _make_kb_repo(kb_entries)

        envelopes = await enrich_timeline_envelopes([event], kb_repo, uuid4())

        loc = envelopes[0].location_ref
        assert loc is not None
        assert loc["name"] == "Thornwall"
        assert loc["status"] == "deprecated"

    @pytest.mark.asyncio
    async def test_deprecated_entity_status(self) -> None:
        """Deprecated KB entries map to 'deprecated' in envelope."""
        event = _make_timeline_event(
            character_refs=[{"id": "e-1", "name": "Old Character"}],
        )
        kb_entries = [_make_kb_entry("Old Character", "deprecated")]
        kb_repo = _make_kb_repo(kb_entries)

        envelopes = await enrich_timeline_envelopes([event], kb_repo, uuid4())

        char = envelopes[0].character_refs[0]
        assert char["status"] == "deprecated"

    @pytest.mark.asyncio
    async def test_null_location_ref(self) -> None:
        """Event with no location produces None location_ref."""
        event = _make_timeline_event(location_ref=None)
        kb_repo = _make_kb_repo([])

        envelopes = await enrich_timeline_envelopes([event], kb_repo, uuid4())

        assert envelopes[0].location_ref is None

    @pytest.mark.asyncio
    async def test_graceful_kb_failure(self) -> None:
        """KB lookup failure does not block envelope creation."""
        event = _make_timeline_event()
        kb_repo = _make_kb_repo([], fail=True)

        envelopes = await enrich_timeline_envelopes([event], kb_repo, uuid4())

        assert len(envelopes) == 1
        # Entity status should be "unknown" since KB lookup failed
        assert envelopes[0].character_refs[0]["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_causes_consequences_split(self) -> None:
        """Comma-separated causes/consequences are split into lists."""
        event = _make_timeline_event(
            causes="Troll invasion, Broken treaty", consequences="Anna's scar, Kai's departure"
        )
        kb_repo = _make_kb_repo([])

        envelopes = await enrich_timeline_envelopes([event], kb_repo, uuid4())

        assert envelopes[0].causes == ["Troll invasion", "Broken treaty"]
        assert envelopes[0].consequences == ["Anna's scar", "Kai's departure"]

    @pytest.mark.asyncio
    async def test_empty_events_list(self) -> None:
        """Empty event list produces empty envelope list."""
        kb_repo = _make_kb_repo([])
        envelopes = await enrich_timeline_envelopes([], kb_repo, uuid4())
        assert envelopes == []


# ---------------------------------------------------------------------------
# Tests — _build_entity_status_map
# ---------------------------------------------------------------------------


class TestBuildEntityStatusMap:
    @pytest.mark.asyncio
    async def test_maps_kb_statuses(self) -> None:
        """KB statuses are correctly mapped to envelope statuses."""
        entries = [
            _make_kb_entry("Anna", "canon"),
            _make_kb_entry("Old Castle", "deprecated"),
            _make_kb_entry("Kai", "draft"),
        ]
        kb_repo = _make_kb_repo(entries)

        status_map = await _build_entity_status_map(kb_repo, uuid4())

        assert status_map["anna"] == "active"
        assert status_map["old castle"] == "deprecated"
        assert status_map["kai"] == "active"

    @pytest.mark.asyncio
    async def test_handles_empty_name(self) -> None:
        """Entities with empty names are skipped."""
        entries = [_make_kb_entry("", "canon"), _make_kb_entry("Valid", "canon")]
        kb_repo = _make_kb_repo(entries)

        status_map = await _build_entity_status_map(kb_repo, uuid4())

        assert "" not in status_map
        assert "valid" in status_map

    @pytest.mark.asyncio
    async def test_graceful_on_failure(self) -> None:
        """Returns empty dict on KB failure."""
        kb_repo = _make_kb_repo([], fail=True)

        status_map = await _build_entity_status_map(kb_repo, uuid4())

        assert status_map == {}


# ---------------------------------------------------------------------------
# Tests — _split_list_field
# ---------------------------------------------------------------------------


class TestSplitListField:
    def test_empty_string(self) -> None:
        assert _split_list_field("") == []

    def test_single_item(self) -> None:
        assert _split_list_field("Battle") == ["Battle"]

    def test_multiple_items(self) -> None:
        assert _split_list_field("A, B, C") == ["A", "B", "C"]

    def test_strips_whitespace(self) -> None:
        assert _split_list_field(" A , B , C ") == ["A", "B", "C"]

    def test_skips_empty_items(self) -> None:
        assert _split_list_field("A,,B,") == ["A", "B"]
