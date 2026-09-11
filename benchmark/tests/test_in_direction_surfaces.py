"""Unit tests for the IN-direction beyond-KB drivers (plan Task 8).

Covers CAP-IN-05..09 (the ``benchmark.drivers.in_direction_surfaces``
half): manual authoring, scope move, timeline SSE (flavor A), wiki
refresh, character-voice SSE (flavor B) — happy path sequence, request
payload shape, parsed-record fields, SSE terminal handling (``[DONE]``
and in-band error frames), and missing-target SKIP. Shared fixtures in
``in_direction_helpers.py``; the KB-core half + HTTP-500 matrix live in
``test_in_direction.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from benchmark.drivers.in_direction_surfaces import (
    CharacterVoiceDriver,
    ManualAuthoringDriver,
    ScopeMoveDriver,
    TimelineExtractionDriver,
    WikiRefreshDriver,
)
from benchmark.drivers.in_records import (
    CharacterVoiceRecord,
    ManualAuthoringRecord,
    ScopeMoveRecord,
    TimelineExtractionRecord,
    VoiceProfile,
    WikiRefreshRecord,
)
from benchmark.tests.client_helpers import ScriptedApi, make_client
from benchmark.tests.in_direction_helpers import (
    ANALYSIS_BODIES,
    ENTRY_BODY,
    JOIN_RESULT_BODY,
    KB,
    NOVEL_ENTRY_BODY,
    NOVEL_ID,
    PREVIEW_BODY,
    REFRESH_BODY,
    RELATIONSHIP_BODY,
    SERIES_ENTRY_BODY,
    STALE_BODY,
    TIMELINE,
    TIMELINE_ERROR_SSE,
    TIMELINE_SSE,
    VOICE_ERROR_SSE,
    VOICE_SSE,
    context,
    invoke,
    router,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from benchmark.drivers.base import CapabilityDriver
    from benchmark.ingest_events import IngestEvent


# ---------------------------------------------------------------------------
# CAP-IN-05 — ManualAuthoringDriver: novel entry, series entry, relationship
# ---------------------------------------------------------------------------


def test_manual_authoring_driver_authors_novel_entry_and_relationship() -> None:
    routes = {
        f"POST {KB}/entries": ENTRY_BODY,
        f"PATCH {KB}/entries/entry-9": {**ENTRY_BODY, "body": "Manuell aktualisiert."},
        f"POST {KB}/relationships": RELATIONSHIP_BODY,
    }

    api, _events, parsed = invoke(ManualAuthoringDriver, routes, targets={"entry_id": "entry-1"})

    assert api.paths() == [
        f"POST {KB}/entries",
        f"PATCH {KB}/entries/entry-9",
        f"POST {KB}/relationships",
    ]
    create_body = cast("dict[str, object]", api.calls[0].body)
    assert create_body["source"] == "benchmark"
    assert create_body["entity_type"] == "character"
    assert api.calls[1].body == {"body": "Manuell aktualisiert."}
    assert api.calls[2].body == {
        "source_id": "entry-9",
        "target_id": "entry-1",
        "rel_type": "related_to",
    }
    assert isinstance(parsed, ManualAuthoringRecord)
    assert parsed.novel_entry.id == "entry-9"
    assert parsed.series_entry is None
    assert parsed.relationship is not None
    assert parsed.relationship.target_id == "entry-1"


def test_manual_authoring_driver_also_authors_series_entry_when_series_targeted() -> None:
    routes = {
        f"POST {KB}/entries": ENTRY_BODY,
        f"PATCH {KB}/entries/entry-9": {**ENTRY_BODY, "body": "Manuell aktualisiert."},
        "POST /api/v1/series/series-1/kb": {**ENTRY_BODY, "id": "entry-s1", "scope": "series"},
        "PATCH /api/v1/series/series-1/kb/entry-s1": {
            **ENTRY_BODY,
            "id": "entry-s1",
            "scope": "series",
            "body": "Manuell aktualisiert.",
        },
        f"POST {KB}/relationships": RELATIONSHIP_BODY,
    }

    api, _events, parsed = invoke(
        ManualAuthoringDriver,
        routes,
        targets={"series_id": "series-1", "entry_id": "entry-1"},
    )

    assert api.paths() == [
        f"POST {KB}/entries",
        f"PATCH {KB}/entries/entry-9",
        "POST /api/v1/series/series-1/kb",
        "PATCH /api/v1/series/series-1/kb/entry-s1",
        f"POST {KB}/relationships",
    ]
    assert isinstance(parsed, ManualAuthoringRecord)
    assert parsed.series_entry is not None
    assert parsed.series_entry.id == "entry-s1"


# ---------------------------------------------------------------------------
# CAP-IN-06 — ScopeMoveDriver: join preview/apply, promote, demote
# ---------------------------------------------------------------------------


def test_scope_move_driver_joins_promotes_and_demotes() -> None:
    routes = {
        "POST /api/v1/series/series-1/novels": PREVIEW_BODY,
        f"POST /api/v1/series/series-1/novels/{NOVEL_ID}/apply": JOIN_RESULT_BODY,
        f"POST {KB}/entry-1/promote": SERIES_ENTRY_BODY,
        f"POST {KB}/entry-1/demote": NOVEL_ENTRY_BODY,
    }

    api, _events, parsed = invoke(
        ScopeMoveDriver,
        routes,
        targets={"series_id": "series-1", "entry_id": "entry-1"},
    )

    assert api.paths() == [
        "POST /api/v1/series/series-1/novels",
        f"POST /api/v1/series/series-1/novels/{NOVEL_ID}/apply",
        f"POST {KB}/entry-1/promote",
        f"POST {KB}/entry-1/demote",
    ]
    assert api.calls[0].body == {"novel_id": NOVEL_ID}
    assert api.calls[1].body == {"position": 1}
    assert api.calls[2].body is None
    assert api.calls[3].body == {"series_id": "series-1"}
    assert isinstance(parsed, ScopeMoveRecord)
    assert parsed == ScopeMoveRecord(
        series_id="series-1",
        canon_empty=True,
        treatment_count=1,
        join_position=1,
        promoted_count=1,
        entry_id="entry-1",
        promoted_scope="series",
        demoted_scope="novel",
    )


@pytest.mark.parametrize(
    ("driver", "required_key"),
    [(ScopeMoveDriver, "series_id"), (WikiRefreshDriver, "entry_id")],
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
# CAP-IN-07 — TimelineExtractionDriver: SSE flavor A + confirm
# ---------------------------------------------------------------------------


def test_timeline_driver_collects_stream_and_confirms_first_expression() -> None:
    routes = {
        f"POST {TIMELINE}/extract": TIMELINE_SSE,
        f"POST {TIMELINE}/extract/confirm": ANALYSIS_BODIES["confirmed_event"],
    }

    api, events, parsed = invoke(TimelineExtractionDriver, routes)

    assert api.paths() == [f"POST {TIMELINE}/extract", f"POST {TIMELINE}/extract/confirm"]
    assert api.calls[0].body == {"chapter_ids": []}
    confirm_body = cast("dict[str, object]", api.calls[1].body)
    assert set(confirm_body) == {
        "expression",
        "event_name",
        "timestamp_raw",
        "chapter_reference",
        "character_names",
        "location_name",
        "confidence",
        "context",
    }
    assert "id" not in confirm_body
    assert isinstance(parsed, TimelineExtractionRecord)
    assert len(parsed.expressions) == 1
    expression = parsed.expressions[0]
    assert expression.id == "ev-1"
    assert expression.expression == "am Morgen des dritten Tages"
    assert expression.character_names == ("Anna Meyer",)
    assert expression.confidence == 0.9
    assert parsed.confirmed_event_id == "event-1"
    assert parsed.confirmed_event_name == "Ritt nach Hamburg"
    assert [event.step for event in events] == ["CAP-IN-07:extract", "CAP-IN-07:confirm"]


def test_timeline_driver_in_band_error_is_error_result() -> None:
    api = ScriptedApi()
    api.respond_with(router({f"POST {TIMELINE}/extract": TIMELINE_ERROR_SSE}))

    result = TimelineExtractionDriver().invoke(context(make_client(api)))

    assert result.status.name == "ERROR"
    assert result.reason is not None and "Novel not found" in result.reason
    assert result.parsed is None


# ---------------------------------------------------------------------------
# CAP-IN-08 — WikiRefreshDriver: refresh + mark-stale
# ---------------------------------------------------------------------------


def test_wiki_refresh_driver_refreshes_then_marks_stale() -> None:
    routes = {
        f"POST /api/v1/novels/{NOVEL_ID}/wiki/summaries/entry-1/refresh": REFRESH_BODY,
        f"POST /api/v1/novels/{NOVEL_ID}/wiki/mark-stale": STALE_BODY,
    }

    api, _events, parsed = invoke(WikiRefreshDriver, routes, targets={"entry_id": "entry-1"})

    assert api.paths() == [
        f"POST /api/v1/novels/{NOVEL_ID}/wiki/summaries/entry-1/refresh",
        f"POST /api/v1/novels/{NOVEL_ID}/wiki/mark-stale",
    ]
    assert api.calls[0].body == {"force": True}
    assert api.calls[1].body == {"prompt_version": None}
    assert isinstance(parsed, WikiRefreshRecord)
    assert parsed == WikiRefreshRecord(
        summary_id="ws-1",
        status="refreshed",
        message="Summary refreshed successfully.",
        affected_count=3,
    )


# ---------------------------------------------------------------------------
# CAP-IN-09 — CharacterVoiceDriver: SSE flavor B
# ---------------------------------------------------------------------------


def test_character_voice_driver_collects_flavor_b_results() -> None:
    api = ScriptedApi()
    api.respond_with(router({f"POST /api/v1/analysis/character-voice/{NOVEL_ID}": VOICE_SSE}))
    events: list[IngestEvent] = []

    result = CharacterVoiceDriver().invoke(
        context(make_client(api, access_token="acc-1"), events=events)
    )

    assert api.paths() == [f"POST /api/v1/analysis/character-voice/{NOVEL_ID}"]
    assert api.calls[0].body == {"chapter_ids": None}
    assert result.status.name == "OK"
    parsed = result.parsed
    assert isinstance(parsed, CharacterVoiceRecord)
    assert parsed.progress_messages == ("2 Figuren gefunden",)
    assert parsed.characters == (
        VoiceProfile(
            character_name="Anna Meyer",
            kb_entry_id="entry-1",
            has_voice_analysis=True,
            distinctiveness_notes="knapper Stil",
        ),
    )
    assert [event.step for event in events] == ["CAP-IN-09"]


def test_character_voice_driver_in_band_error_is_error_result() -> None:
    api = ScriptedApi()
    api.respond_with(router({f"POST /api/v1/analysis/character-voice/{NOVEL_ID}": VOICE_ERROR_SSE}))

    result = CharacterVoiceDriver().invoke(context(make_client(api)))

    assert result.status.name == "ERROR"
    assert result.reason is not None and "Character-voice analysis failed." in result.reason
    assert result.parsed is None
