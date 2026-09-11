"""Unit tests for the scoring-phase KB-state fetch (``fetch_scored_kb``).

The build-quality scorer's "actual KB" input is NOT the driven capability
answers: ``fetch_scored_kb`` collects the full entry listing (CAP-OUT-01
endpoint shape, paginated) plus EVERY entry's detail + relationships
(CAP-OUT-03 endpoint shapes) itself — scoring has data regardless of the
user's ``--capabilities`` selection. Failures propagate (no fabricated
state). Scripted MockTransport per the OUT-direction test precedent;
shared fixtures in ``out_direction_helpers.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from benchmark.client import ApiError
from benchmark.drivers.out_records import EntityDetailRecord, EntrySummary
from benchmark.runner_scoring import fetch_scored_kb
from benchmark.tests.artifacts_helpers import make_config
from benchmark.tests.client_helpers import RecordedCall, ScriptedApi, make_client
from benchmark.tests.out_direction_helpers import (
    ENTRY_A,
    ENTRY_B,
    KB,
    KB_ENTRIES,
    LIST_PAGE_ONE,
    LIST_PAGE_TWO,
    LIST_SINGLE_PAGE,
    NOVEL_ID,
    REL_BODY,
    RELATIONSHIPS_BODY,
    corpus_with,
    router,
)

if TYPE_CHECKING:
    from benchmark.ingest_events import IngestEvent
    from benchmark.runner_scoring import ScoredKb

DETAIL_9 = f"{KB}/entries/entry-9"
RELATIONSHIPS_9 = f"{KB}/entries/entry-9/relationships"
DETAIL_2 = f"{KB}/entries/entry-2"
RELATIONSHIPS_2 = f"{KB}/entries/entry-2/relationships"

# The API returns relationship edges as IDs only — source_name/target_name
# are always None; the fetch enriches them from the paginated entry listing.
UNNAMED_RELATIONSHIPS_BODY: list[dict[str, object]] = [
    {**REL_BODY, "source_name": None, "target_name": None, "target_id": "entry-2"},
    {
        **REL_BODY,
        "id": "rel-2",
        "rel_type": "related_to",
        "source_name": None,
        "target_name": None,
    },  # target_id "entry-1" is NOT in the listing
]


def _fetch(api: ScriptedApi, events: list[IngestEvent] | None = None) -> ScoredKb:
    """Production-shape call: raw runner args, the fetch builds its own ctx."""
    return fetch_scored_kb(
        make_client(api, access_token="acc-1"),
        corpus_with(()),
        NOVEL_ID,
        {},
        make_config(),
        events if events is not None else [],
        {},
    )


def test_fetch_collects_all_entries_with_details_and_relationships() -> None:
    routes = {
        f"GET {KB_ENTRIES}": LIST_SINGLE_PAGE,
        f"GET {DETAIL_9}": ENTRY_A,
        f"GET {RELATIONSHIPS_9}": RELATIONSHIPS_BODY,
        f"GET {DETAIL_2}": ENTRY_B,
        f"GET {RELATIONSHIPS_2}": [],
    }
    api = ScriptedApi()
    api.respond_with(router(routes))
    events: list[IngestEvent] = []

    kb = _fetch(api, events)

    assert api.paths() == [
        f"GET {KB_ENTRIES}",
        f"GET {DETAIL_9}",
        f"GET {RELATIONSHIPS_9}",
        f"GET {DETAIL_2}",
        f"GET {RELATIONSHIPS_2}",
    ]
    assert api.calls[0].params == {"page": "1", "page_size": "100"}
    assert kb.entries == (
        EntrySummary(
            id="entry-9",
            name="Benchmark Figur",
            entity_type="character",
            slug="benchmark-figur",
            status="draft",
            review_status="approved",
        ),
        EntrySummary(
            id="entry-2",
            name="HafenCity",
            entity_type="location",
            slug="hafen city",
            status="draft",
            review_status="approved",
        ),
    )
    assert [record.entry.id for record in kb.details] == ["entry-9", "entry-2"]
    anna = kb.details[0]
    assert isinstance(anna, EntityDetailRecord)
    assert [edge.rel_type for edge in anna.relationships] == ["lives_in"]
    # names the API already provides pass through untouched (never overwritten)
    edge = anna.relationships[0]
    assert edge.source_name == "Anna Meyer"
    assert edge.target_name == "HafenCity"
    # the inverse-suggestion probe is a CAP-OUT-03 capability probe, not KB
    # state — never fetched here, never fabricated
    assert anna.inverse_of is None
    assert anna.inverse_rel_type is None
    assert [event.step for event in events] == [
        "scoring:browse-page-1",
        "scoring:entry:entry-9",
        "scoring:relationships:entry-9",
        "scoring:entry:entry-2",
        "scoring:relationships:entry-2",
    ]


def test_relationship_names_enriched_from_the_entry_listing() -> None:
    routes = {
        f"GET {KB_ENTRIES}": LIST_SINGLE_PAGE,
        f"GET {DETAIL_9}": ENTRY_A,
        f"GET {RELATIONSHIPS_9}": UNNAMED_RELATIONSHIPS_BODY,
        f"GET {DETAIL_2}": ENTRY_B,
        f"GET {RELATIONSHIPS_2}": [],
    }
    api = ScriptedApi()
    api.respond_with(router(routes))

    kb = _fetch(api)

    edges = kb.details[0].relationships
    # names resolved against the listing's id→name map …
    assert [(edge.source_name, edge.target_name) for edge in edges] == [
        ("Benchmark Figur", "HafenCity"),
        # … an ID outside the listing stays None (absence, never fabrication)
        ("Benchmark Figur", None),
    ]


def test_fetch_pages_until_total_is_reached() -> None:
    api = ScriptedApi()
    pages = [LIST_PAGE_ONE, LIST_PAGE_TWO]

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        key = f"{call.method} {call.path}"
        if key == f"GET {KB_ENTRIES}":
            return httpx.Response(200, json=pages.pop(0))
        if key.endswith("/relationships"):
            return httpx.Response(200, json=[])
        if key.startswith(f"GET {KB}/entries/"):
            return httpx.Response(200, json=ENTRY_A)
        raise AssertionError(f"unexpected call: {key}")

    api.respond_with(responder)

    kb = _fetch(api)

    assert api.calls[0].params == {"page": "1", "page_size": "100"}
    assert api.calls[1].params == {"page": "2", "page_size": "100"}
    assert len(kb.entries) == 101
    assert len(kb.details) == 101  # EVERY listed entry gets its detail fetch


def test_empty_kb_yields_an_empty_scored_state() -> None:
    routes: dict[str, object] = {
        f"GET {KB_ENTRIES}": {"items": [], "total": 0, "page": 1, "page_size": 100}
    }
    api = ScriptedApi()
    api.respond_with(router(routes))
    events: list[IngestEvent] = []

    kb = _fetch(api, events)

    assert kb.entries == ()
    assert kb.details == ()
    assert [event.step for event in events] == ["scoring:browse-page-1"]


def test_entry_list_failure_propagates_without_fabricating_state() -> None:
    api = ScriptedApi()
    api.respond_with(router({f"GET {KB_ENTRIES}": 500}))

    with pytest.raises(ApiError):
        _fetch(api)

    assert api.paths() == [f"GET {KB_ENTRIES}"]  # fail fast, no detail fan-out


def test_detail_failure_propagates_mid_fetch() -> None:
    routes = {
        f"GET {KB_ENTRIES}": LIST_SINGLE_PAGE,
        f"GET {DETAIL_9}": ENTRY_A,
        f"GET {RELATIONSHIPS_9}": 500,
    }
    api = ScriptedApi()
    api.respond_with(router(routes))

    with pytest.raises(ApiError):
        _fetch(api)

    assert api.paths()[-1] == f"GET {RELATIONSHIPS_9}"
