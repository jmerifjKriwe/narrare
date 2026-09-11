"""ResolutionDriver 409-tolerance tests (CAP-IN-10, ADR-085 fix wave).

Transitive duplicate groups (3 entries → 3 expected pairs) make later
endorses conflict STRUCTURALLY: every endorse re-validates via a fresh
``analyze(refresh=True)`` whose snapshot excludes deprecated losers, so
once merge #1 deprecated a shared endpoint the remaining suggestions
vanish from the re-score and the endorse endpoint answers ``409
Conflict`` (endorse_service re-validation contract). Tolerating the 409
as "already reconciled via a prior pair" keeps the capability OK, keeps
the suggestion set intact for precision/recall scoring, and records the
skip on the parsed record. Split from ``test_in_direction.py`` per
RULE-04 (file-size limit); fixture helpers shared via
``in_direction_helpers.py``. The non-409 failure path stays pinned by
the HTTP-500 matrix there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from benchmark.drivers.base import CapabilityStatus
from benchmark.drivers.in_direction import ResolutionDriver
from benchmark.drivers.in_records import (
    MergeResult,
    ResolutionRecord,
    SkippedEndorse,
)
from benchmark.tests.client_helpers import RecordedCall, ScriptedApi, make_client
from benchmark.tests.in_direction_helpers import KB, context

if TYPE_CHECKING:
    from benchmark.ingest_events import IngestEvent

_CONFLICT_DETAIL = (
    "failed re-validation: stale, rejected, or below the review band — re-run the analysis"
)

_BODIES: dict[str, object] = {
    "analyze": {
        "suggestions": [
            {
                "suggestion_id": "sug-1",
                "entry_a_id": "entry-a",
                "entry_b_id": "entry-b",
                "name_a": "Anna Meyer",
                "name_b": "Anna Meyer",
                "confidence": 0.97,
                "band": "AUTO_ELIGIBLE",
                "auto_merge_eligible": True,
                "signals": [],
                "adjudication_note": None,
            },
            {
                "suggestion_id": "sug-2",
                "entry_a_id": "entry-a",
                "entry_b_id": "entry-c",
                "name_a": "Anna Meyer",
                "name_b": "Anna",
                "confidence": 0.93,
                "band": "REVIEW",
                "auto_merge_eligible": False,
                "signals": [],
                "adjudication_note": None,
            },
            {
                "suggestion_id": "sug-3",
                "entry_a_id": "entry-b",
                "entry_b_id": "entry-c",
                "name_a": "Anna Meyer",
                "name_b": "Anna",
                "confidence": 0.91,
                "band": "REVIEW",
                "auto_merge_eligible": False,
                "signals": [],
                "adjudication_note": None,
            },
        ],
        "stats": {"review": 2, "auto_eligible": 1, "suppressed": 0},
        "cache_hit": False,
    },
    "merge": {
        "survivor_id": "entry-a",
        "loser_id": "entry-b",
        "merged_fact_keys": ["description"],
        "repointed_relationships": 0,
        "skipped_relationships": 0,
        "conflicts": [],
    },
}


def _transitive_responder(_index: int, call: RecordedCall) -> httpx.Response:
    """3-entry group: sug-1 merges (deprecates entry-b), sug-2/sug-3 409."""
    key = f"{call.method} {call.path}"
    if key == f"POST {KB}/resolution/analyze":
        return httpx.Response(200, json=_BODIES["analyze"])
    if key == f"POST {KB}/resolution/suggestions/sug-1/endorse":
        return httpx.Response(200, json=_BODIES["merge"])
    suggestion_id = call.path.split("/")[-2]
    return httpx.Response(
        409,
        json={
            "detail": f"Suggestion {suggestion_id} {_CONFLICT_DETAIL}",
            "code": "CONFLICT",
        },
    )


def test_transitive_duplicate_group_conflicts_are_tolerated_skips() -> None:
    api = ScriptedApi()
    api.respond_with(_transitive_responder)
    events: list[IngestEvent] = []

    result = ResolutionDriver().invoke(
        context(make_client(api, access_token="acc-1"), events=events)
    )

    assert result.status is CapabilityStatus.OK, result.reason
    assert api.paths() == [
        f"POST {KB}/resolution/analyze",
        f"POST {KB}/resolution/suggestions/sug-1/endorse",
        f"POST {KB}/resolution/suggestions/sug-2/endorse",
        f"POST {KB}/resolution/suggestions/sug-3/endorse",
    ]
    parsed = result.parsed
    assert isinstance(parsed, ResolutionRecord)
    # The suggestion set stays intact for precision/recall scoring.
    assert [s.suggestion_id for s in parsed.suggestions] == ["sug-1", "sug-2", "sug-3"]
    assert parsed.merges == (
        MergeResult(
            survivor_id="entry-a",
            loser_id="entry-b",
            merged_fact_keys=("description",),
            repointed_relationships=0,
            skipped_relationships=0,
        ),
    )
    assert parsed.skips == (
        SkippedEndorse(suggestion_id="sug-2", detail=f"Suggestion sug-2 {_CONFLICT_DETAIL}"),
        SkippedEndorse(suggestion_id="sug-3", detail=f"Suggestion sug-3 {_CONFLICT_DETAIL}"),
    )
    # The sink records completed exchanges only (shapes contract: ApiError
    # propagates unrecorded) — the 409 skip evidence lives on the parsed
    # record's skips, not in the event sink.
    assert [event.step for event in events] == [
        "CAP-IN-10:analyze",
        "CAP-IN-10:endorse",
    ]


def test_skipped_suggestions_are_resolution_suggestions() -> None:
    """Every skipped endorse id maps back to a surfaced suggestion."""
    api = ScriptedApi()
    api.respond_with(_transitive_responder)

    result = ResolutionDriver().invoke(context(make_client(api, access_token="acc-1")))

    assert result.status is CapabilityStatus.OK
    parsed = result.parsed
    assert isinstance(parsed, ResolutionRecord)
    surfaced = {s.suggestion_id for s in parsed.suggestions}
    assert all(skip.suggestion_id in surfaced for skip in parsed.skips)
