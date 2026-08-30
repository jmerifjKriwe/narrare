"""Unit tests for the IN-direction KB-core drivers (plan Task 8).

Covers CAP-IN-01..04 (the ``benchmark.drivers.in_direction`` half: happy
path sequence, request payload shape, parsed-record fields, missing-target
SKIP, plus the HTTP-500→ERROR matrix over ALL nine drivers). The
CAP-IN-05..09 tests live in ``test_in_direction_surfaces.py``; shared
fixtures in ``in_direction_helpers.py``. The T7 carry-forward acceptance
is pinned here: all nine ``DRIVERS`` entries are real classes whose
names match the registry ``driver_name`` with zero placeholders among
them (since Task 9 only the 7 CHK entries remain placeholders).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import httpx
import pytest

from benchmark.capabilities import CAPABILITIES, capability
from benchmark.drivers import DRIVERS, PlaceholderDriver
from benchmark.drivers.base import CapabilityStatus
from benchmark.drivers.in_direction import (
    ASSIST_FIELD_KEY,
    ASSIST_NAME,
    IN_DIRECTION_DRIVERS,
    AssistSessionDriver,
    CharacterVoiceDriver,
    ExtractionDriver,
    ImproveAnalysisDriver,
    ManualAuthoringDriver,
    ScopeMoveDriver,
    TimelineExtractionDriver,
    WikiRefreshDriver,
    WorldbuildingDriver,
)
from benchmark.drivers.in_records import (
    AssistSessionRecord,
    ExtractionRecord,
    ImproveRecord,
    WorldbuildingRecord,
)
from benchmark.tests.client_helpers import ScriptedApi, make_client
from benchmark.tests.in_direction_helpers import (
    ANALYSIS_BODIES,
    APPLY_BODY,
    EXTRACT_BODY,
    IMPROVE_APPLY_BODY,
    KB,
    SESSION_BODY,
    WORLDBUILDING_APPLY_BODY,
    context,
    invoke,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from benchmark.drivers.base import CapabilityDriver


# ---------------------------------------------------------------------------
# T7 carry-forward acceptance: the 9 replaced entries are real and pinned
# ---------------------------------------------------------------------------


def test_t8_carry_forward_all_nine_replaced_and_names_pinned() -> None:
    assert len(IN_DIRECTION_DRIVERS) == 9
    assert set(IN_DIRECTION_DRIVERS) == {
        spec.cap_id for spec in CAPABILITIES if spec.direction == "in"
    }
    for cap_id, driver in IN_DIRECTION_DRIVERS.items():
        spec = capability(cap_id)
        assert spec.direction == "in"
        assert DRIVERS[cap_id] is driver
        assert driver.__name__ == spec.driver_name
        assert driver is not PlaceholderDriver


def test_t8_carry_forward_check_entries_still_placeholder() -> None:
    """Task 9 advanced the boundary: only the 7 CHK entries still wait."""
    for spec in CAPABILITIES:
        if spec.direction == "check":
            assert DRIVERS[spec.cap_id] is PlaceholderDriver
        else:
            assert DRIVERS[spec.cap_id] is not PlaceholderDriver


def test_capability_context_targets_defaults_to_empty_map() -> None:
    ctx = context(make_client(ScriptedApi()))

    assert ctx.targets == {}


# ---------------------------------------------------------------------------
# CAP-IN-01 — ExtractionDriver (post-build re-invocation; build path = ingest)
# ---------------------------------------------------------------------------


def test_extraction_driver_reinvokes_extract_then_endorses_all() -> None:
    routes = {
        f"POST {KB}/extract/chapter-1": EXTRACT_BODY,
        f"POST {KB}/extract/apply": APPLY_BODY,
    }

    api, events, parsed = invoke(ExtractionDriver, routes, targets={"chapter_id": "chapter-1"})

    assert api.paths() == [
        f"POST {KB}/extract/chapter-1",
        f"POST {KB}/extract/apply",
    ]
    apply_body = cast("dict[str, object]", api.calls[1].body)
    items = cast("list[object]", apply_body["items"])
    assert len(items) == 2
    first = cast("dict[str, object]", items[0])
    assert set(first) == {
        "item_type",
        "name",
        "entity_type",
        "proposed_content",
        "target_entity_id",
        "relationship_type",
        "related_entity_name",
        "source_text",
    }
    assert "confidence" not in first
    assert isinstance(parsed, ExtractionRecord)
    assert parsed.chapter_id == "chapter-1"
    assert parsed.analysis_notes == "2 Kandidaten"
    assert [candidate.name for candidate in parsed.candidates] == ["Anna Meyer", "Anna Meyer"]
    assert parsed.candidates[0].confidence == 0.97
    assert parsed.candidates[1].relationship_type == "partner_of"
    assert parsed.created == ("entry-9",)
    assert parsed.updated == ("entry-2",)
    assert [event.step for event in events] == ["CAP-IN-01:extract", "CAP-IN-01:apply"]


def test_extraction_driver_without_chapter_target_is_skipped_structural() -> None:
    api = ScriptedApi()

    result = ExtractionDriver().invoke(context(make_client(api)))

    assert result.status.name == "SKIPPED"
    assert result.reason is not None and "chapter_id" in result.reason
    assert api.calls == []


# ---------------------------------------------------------------------------
# CAP-IN-02 — AssistSessionDriver: full six-step session lifecycle
# ---------------------------------------------------------------------------


def test_assist_session_driver_drives_full_session_lifecycle() -> None:
    routes = {
        f"POST {KB}/sessions": SESSION_BODY,
        f"POST {KB}/sessions/session-1/suggest/name": {
            "session": SESSION_BODY,
            "suggestion": "Anna Meyer",
        },
        f"POST {KB}/sessions/session-1/interview": {
            "session": SESSION_BODY,
            "question": "Woher stammt Anna?",
        },
        f"POST {KB}/sessions/session-1/enhance": {
            "session": SESSION_BODY,
            "enhancement": "erweitert",
        },
        f"PATCH {KB}/sessions/session-1/fields/name": SESSION_BODY,
        f"POST {KB}/sessions/session-1/complete": {
            "session": {**SESSION_BODY, "status": "complete"},
            "entry_id": "entry-7",
        },
    }

    api, events, parsed = invoke(AssistSessionDriver, routes)

    assert api.paths() == [
        f"POST {KB}/sessions",
        f"POST {KB}/sessions/session-1/suggest/{ASSIST_FIELD_KEY}",
        f"POST {KB}/sessions/session-1/interview",
        f"POST {KB}/sessions/session-1/enhance",
        f"PATCH {KB}/sessions/session-1/fields/{ASSIST_FIELD_KEY}",
        f"POST {KB}/sessions/session-1/complete",
    ]
    assert api.calls[0].body == {"entity_type": "character"}
    assert api.calls[4].body == {"value": ASSIST_NAME}
    assert isinstance(parsed, AssistSessionRecord)
    assert parsed.session_id == "session-1"
    assert parsed.entity_type == "character"
    assert parsed.status == "complete"
    assert parsed.entry_id == "entry-7"
    assert [event.step for event in events] == [f"CAP-IN-02:step-{i}" for i in range(1, 7)]


# ---------------------------------------------------------------------------
# CAP-IN-03 — ImproveAnalysisDriver: analyze then apply all suggestion ids
# ---------------------------------------------------------------------------


def test_improve_driver_analyzes_then_applies_all_suggestions() -> None:
    routes = {
        f"POST {KB}/entities/entry-1/improve": ANALYSIS_BODIES["improve"],
        f"POST {KB}/entities/entry-1/improve/apply": IMPROVE_APPLY_BODY,
    }

    api, _events, parsed = invoke(ImproveAnalysisDriver, routes, targets={"entry_id": "entry-1"})

    assert api.paths() == [
        f"POST {KB}/entities/entry-1/improve",
        f"POST {KB}/entities/entry-1/improve/apply",
    ]
    assert api.calls[0].body is None
    assert api.calls[1].body == {"suggestion_ids": [0, 1]}
    assert isinstance(parsed, ImproveRecord)
    assert parsed == ImproveRecord(
        entry_id="entry-1",
        suggestion_count=2,
        completeness_score=0.5,
        overall_assessment="solide",
        applied_count=2,
        apply_success=True,
        apply_message="2 Verbesserungen angewendet",
    )


# ---------------------------------------------------------------------------
# CAP-IN-04 — WorldbuildingDriver: analyze then apply connection indices
# ---------------------------------------------------------------------------


def test_worldbuilding_driver_applies_connection_suggestions() -> None:
    routes = {
        f"POST {KB}/worldbuilding/analyze": ANALYSIS_BODIES["worldbuilding"],
        f"POST {KB}/worldbuilding/apply": WORLDBUILDING_APPLY_BODY,
    }

    api, _events, parsed = invoke(WorldbuildingDriver, routes)

    assert api.paths() == [
        f"POST {KB}/worldbuilding/analyze",
        f"POST {KB}/worldbuilding/apply",
    ]
    assert api.calls[0].body == {}
    assert api.calls[1].body == {
        "finding_indices": [2],
        "analysis": ANALYSIS_BODIES["worldbuilding"],
    }
    assert isinstance(parsed, WorldbuildingRecord)
    assert parsed == WorldbuildingRecord(
        gap_count=1,
        connection_count=1,
        consistency_count=0,
        worldbuilding_score=0.75,
        applied_indices=(2,),
        created_count=1,
        failed_count=0,
    )


# ---------------------------------------------------------------------------
# Structural targets — missing ingest-discovered ids are SKIPPED, not made up
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("driver", "required_key"),
    [(ExtractionDriver, "chapter_id"), (ImproveAnalysisDriver, "entry_id")],
)
def test_missing_target_is_skipped_structural(
    driver: Callable[[], CapabilityDriver], required_key: str
) -> None:
    api = ScriptedApi()  # any call would be unscripted → must NOT be called

    result = driver().invoke(context(make_client(api)))

    assert result.status.name == "SKIPPED"
    assert result.reason is not None and required_key in result.reason
    assert api.calls == []


# ---------------------------------------------------------------------------
# Error paths — HTTP 500 becomes ERROR with a reason, for every driver
# ---------------------------------------------------------------------------

_ALL_NINE: tuple[tuple[Callable[[], CapabilityDriver], str, dict[str, str]], ...] = (
    (ExtractionDriver, "CAP-IN-01", {"chapter_id": "chapter-1"}),
    (AssistSessionDriver, "CAP-IN-02", {}),
    (ImproveAnalysisDriver, "CAP-IN-03", {"entry_id": "entry-1"}),
    (WorldbuildingDriver, "CAP-IN-04", {}),
    (ManualAuthoringDriver, "CAP-IN-05", {"entry_id": "entry-1"}),
    (ScopeMoveDriver, "CAP-IN-06", {"series_id": "series-1", "entry_id": "entry-1"}),
    (TimelineExtractionDriver, "CAP-IN-07", {}),
    (WikiRefreshDriver, "CAP-IN-08", {"entry_id": "entry-1"}),
    (CharacterVoiceDriver, "CAP-IN-09", {}),
)


@pytest.mark.parametrize(
    ("driver", "cap_id", "targets"),
    _ALL_NINE,
    ids=[cap_id for _driver, cap_id, _targets in _ALL_NINE],
)
def test_http_500_surfaces_as_error_result(
    driver: Callable[[], CapabilityDriver], cap_id: str, targets: dict[str, str]
) -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _index, _call: httpx.Response(500, json={"detail": "boom", "code": "INTERNAL"})
    )

    result = driver().invoke(context(make_client(api), targets=targets))

    assert result.cap_id == cap_id
    assert result.status is CapabilityStatus.ERROR
    assert result.reason is not None and "boom" in result.reason
    assert result.parsed is None
