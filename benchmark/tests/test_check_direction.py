"""Unit tests for the CHECK-direction REST drivers (plan Task 10).

Covers CAP-CHK-01..04 (novel KB consistency, series canon contradiction,
series voice drift, temporal timeline consistency): happy-path request
payloads, parsed-record fields, series-target structural skips, and the
HTTP-500→ERROR matrix over all four REST drivers. The CAP-CHK-05..07
SSE tests live in ``test_check_direction_streams.py``; shared fixtures in
``check_direction_helpers.py``. The Task-10 carry-forward acceptance is
pinned here: all seven CHK ``DRIVERS`` entries are real classes whose
names match the registry ``driver_name`` — completing the 26-entry
registry (see ``test_capabilities.py`` for the completion pin).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from benchmark.capabilities import CAPABILITIES, capability
from benchmark.drivers import DRIVERS
from benchmark.drivers.base import CapabilityStatus
from benchmark.drivers.check_direction import (
    CHECK_DIRECTION_DRIVERS,
    ConsistencyCheckDriver,
    TemporalConsistencyDriver,
)
from benchmark.drivers.check_direction_series import (
    SeriesConsistencyDriver,
    SeriesVoiceDriftDriver,
)
from benchmark.drivers.check_records import (
    ConsistencyCheckRecord,
    SeriesConsistencyRecord,
    SeriesVoiceDriftRecord,
    TemporalConsistencyRecord,
)
from benchmark.tests.check_direction_helpers import (
    CHAPTER_ID,
    CHECK_BODIES,
    CHK_CHECK,
    NOVEL_ID,
    SERIES_CONSISTENCY,
    SERIES_ID,
    SERIES_SNAPSHOT,
    SERIES_VOICE_DRIFT,
    TEMPORAL,
    context,
    invoke,
)
from benchmark.tests.client_helpers import ScriptedApi, make_client

if TYPE_CHECKING:
    from collections.abc import Callable

    from benchmark.drivers.base import CapabilityDriver


# ---------------------------------------------------------------------------
# Task-10 carry-forward acceptance: the 7 replaced entries are real + pinned
# ---------------------------------------------------------------------------


def test_t10_carry_forward_all_seven_replaced_and_names_pinned() -> None:
    assert len(CHECK_DIRECTION_DRIVERS) == 7
    assert set(CHECK_DIRECTION_DRIVERS) == {
        spec.cap_id for spec in CAPABILITIES if spec.direction == "check"
    }
    for cap_id, driver in CHECK_DIRECTION_DRIVERS.items():
        spec = capability(cap_id)
        assert spec.direction == "check"
        assert DRIVERS[cap_id] is driver
        assert driver.__name__ == spec.driver_name


def test_t10_registry_shapes_match_the_driven_invocation_shapes() -> None:
    for spec in CAPABILITIES:
        if spec.direction != "check":
            continue
        if spec.cap_id in ("CAP-CHK-05", "CAP-CHK-06", "CAP-CHK-07"):
            assert spec.shape == "sse" and spec.sse_flavor == "B"
        else:
            assert spec.shape == "rest" and spec.sse_flavor is None


# ---------------------------------------------------------------------------
# CAP-CHK-01 — ConsistencyCheckDriver: full-refresh consistency report
# ---------------------------------------------------------------------------


def test_consistency_check_driver_posts_refresh_body_and_parses_issues() -> None:
    routes = {f"POST {CHK_CHECK}": CHECK_BODIES["consistency"]}

    api, events, parsed = invoke(ConsistencyCheckDriver, routes)

    assert api.paths() == [f"POST {CHK_CHECK}"]
    # Deterministic full report: all three stages + refresh (10-min TTL cache).
    assert api.calls[0].body == {
        "entity_types": None,
        "include_entry_internal": True,
        "include_asymmetry": True,
        "include_cross_entity": True,
        "refresh": True,
    }
    assert isinstance(parsed, ConsistencyCheckRecord)
    assert parsed.novel_id == NOVEL_ID
    assert parsed.entity_count == 3
    assert parsed.suppressed_count == 2
    assert [issue.category for issue in parsed.issues] == [
        "entry_internal",
        "relationship_asymmetry",
    ]
    first = parsed.issues[0]
    assert first.finding_index == 0
    assert first.entity_names == ("Anna Meyer",)
    assert first.contradiction == "Geburtsjahr 1990 widerspricht 1985."
    assert first.suggested_resolution is None
    assert first.severity == "major"
    assert first.confidence == 0.9
    # Summary dict is key-sorted tuple pairs (deterministic record equality).
    assert parsed.summary == (("asymmetry", 1), ("cross_entity", 0), ("entry_internal", 1))
    assert [event.step for event in events] == ["CAP-CHK-01"]


# ---------------------------------------------------------------------------
# CAP-CHK-02 — SeriesConsistencyDriver: canon check + snapshot read-back
# ---------------------------------------------------------------------------


def test_series_consistency_driver_checks_then_reads_snapshot() -> None:
    routes = {
        f"POST {SERIES_CONSISTENCY}": CHECK_BODIES["series_consistency"],
        f"GET {SERIES_SNAPSHOT}": CHECK_BODIES["series_snapshot"],
    }

    api, _events, parsed = invoke(SeriesConsistencyDriver, routes, targets={"series_id": SERIES_ID})

    assert api.paths() == [f"POST {SERIES_CONSISTENCY}", f"GET {SERIES_SNAPSHOT}"]
    assert api.calls[0].body == {"novel_id": NOVEL_ID}
    assert isinstance(parsed, SeriesConsistencyRecord)
    assert parsed.series_id == SERIES_ID
    assert parsed.novel_id == NOVEL_ID
    assert parsed.summary == "Zwei Widersprueche gefunden."
    assert parsed.canon_entry_count == 5
    assert parsed.chapter_count == 2
    assert [(c.canon_entry_slug, c.severity) for c in parsed.conflicts] == [
        ("character-anna-herkunft", "error"),
        ("location-hafen-lage", "warning"),
    ]
    conflict = parsed.conflicts[0]
    assert conflict.canon_entry_name == "Anna — Herkunft"
    assert conflict.chapter_text_excerpt == "Anna kam aus Berlin."
    assert conflict.canon_statement == "Anna kommt aus Hamburg."
    assert conflict.explanation == "Beide Aussagen koennen nicht gleichzeitig gelten."
    snapshot = parsed.snapshot
    assert snapshot.generated_at == "2026-08-27T00:00:00"
    assert snapshot.stale is False
    assert snapshot.has_consistency is True
    assert snapshot.has_voice_drift is True


def test_series_consistency_driver_without_series_target_is_skipped_structural() -> None:
    api = ScriptedApi()  # any call would be unscripted → must NOT be called

    result = SeriesConsistencyDriver().invoke(context(make_client(api)))

    assert result.status is CapabilityStatus.SKIPPED
    assert result.reason is not None and "series_id" in result.reason
    assert api.calls == []


# ---------------------------------------------------------------------------
# CAP-CHK-03 — SeriesVoiceDriftDriver: series narrator drift vs baseline
# ---------------------------------------------------------------------------


def test_series_voice_drift_driver_parses_full_drift_result() -> None:
    routes = {f"POST {SERIES_VOICE_DRIFT}": CHECK_BODIES["series_voice_drift"]}

    api, _events, parsed = invoke(SeriesVoiceDriftDriver, routes, targets={"series_id": SERIES_ID})

    assert api.paths() == [f"POST {SERIES_VOICE_DRIFT}"]
    assert api.calls[0].body == {"novel_id": NOVEL_ID, "chapter_ids": None}
    assert isinstance(parsed, SeriesVoiceDriftRecord)
    assert parsed.series_id == SERIES_ID
    assert parsed.novel_id == NOVEL_ID
    assert parsed.no_profile_reason is None
    result = parsed.result
    assert result is not None
    assert result.novel_id == NOVEL_ID
    assert [(t.chapter_id, t.match_subscore, t.band) for t in result.trend] == [
        (CHAPTER_ID, 88.0, "stable"),
        ("chapter-2", 61.0, "moderate"),
    ]
    assert result.trend[0].per_metric_deltas == (("avg_sentence_length", 0.12),)
    jump = result.jumps[0]
    assert jump.from_chapter_id == CHAPTER_ID
    assert jump.to_chapter_id == "chapter-2"
    assert jump.jumped_metrics == ("avg_sentence_length",)
    assert jump.magnitude == 0.4
    assert result.overall_match_score == 74.5
    assert result.overall_band == "minor"
    verdict = result.drift
    assert verdict.drift_type == "inconsistency"
    assert verdict.confidence == 0.8
    assert verdict.longitudinal_reasons == ("Sprung in der Satzlaenge",)
    assert verdict.per_chapter_notes == (("chapter-2", "Deutlich kuerzere Saetze."),)
    assert verdict.suggested_attention == ("chapter-2",)


def test_series_voice_drift_driver_graceful_no_profile() -> None:
    routes = {f"POST {SERIES_VOICE_DRIFT}": CHECK_BODIES["series_voice_no_profile"]}

    api, _events, parsed = invoke(SeriesVoiceDriftDriver, routes, targets={"series_id": SERIES_ID})

    assert api.paths() == [f"POST {SERIES_VOICE_DRIFT}"]
    assert isinstance(parsed, SeriesVoiceDriftRecord)
    assert parsed.result is None
    assert parsed.no_profile_reason == "no_stored_profile"


def test_series_voice_drift_driver_without_series_target_is_skipped_structural() -> None:
    api = ScriptedApi()

    result = SeriesVoiceDriftDriver().invoke(context(make_client(api)))

    assert result.status is CapabilityStatus.SKIPPED
    assert result.reason is not None and "series_id" in result.reason
    assert api.calls == []


# ---------------------------------------------------------------------------
# CAP-CHK-04 — TemporalConsistencyDriver: timeline duration/consistency
# ---------------------------------------------------------------------------


def test_temporal_consistency_driver_gets_and_parses_issues() -> None:
    routes = {f"GET {TEMPORAL}": CHECK_BODIES["temporal"]}

    api, _events, parsed = invoke(TemporalConsistencyDriver, routes)

    assert api.paths() == [f"GET {TEMPORAL}"]
    assert api.calls[0].body is None  # GET — no request body
    assert isinstance(parsed, TemporalConsistencyRecord)
    assert parsed.deterministic_pass is False
    assert parsed.overall_assessment == "Zwei Probleme gefunden."
    assert [(issue.rule_id, issue.source) for issue in parsed.issues] == [
        ("duration_impossibility", "deterministic"),
        ("llm_validation", "llm"),
    ]
    issue = parsed.issues[0]
    assert issue.severity == "error"
    assert issue.event_ids == ("event-1", "event-2")
    assert issue.description == "Unmoegliche Dauer zwischen den Ereignissen."
    assert issue.suggestion == "Zeitangaben der Ereignisse anpassen."


# ---------------------------------------------------------------------------
# Error paths — HTTP 500 becomes ERROR with a reason, for every REST driver
# ---------------------------------------------------------------------------


def _all_rest() -> tuple[tuple[Callable[[], CapabilityDriver], str, dict[str, str]], ...]:
    return (
        (ConsistencyCheckDriver, "CAP-CHK-01", {}),
        (SeriesConsistencyDriver, "CAP-CHK-02", {"series_id": SERIES_ID}),
        (SeriesVoiceDriftDriver, "CAP-CHK-03", {"series_id": SERIES_ID}),
        (TemporalConsistencyDriver, "CAP-CHK-04", {}),
    )


_ALL_REST = _all_rest()


@pytest.mark.parametrize(
    ("driver", "cap_id", "targets"),
    _ALL_REST,
    ids=[cap_id for _driver, cap_id, _targets in _ALL_REST],
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
