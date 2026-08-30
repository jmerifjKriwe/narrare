"""Unit tests for the OUT-direction KB-core drivers (plan Task 9).

Covers CAP-OUT-01/02 (browse + search, both paginated) plus the
Task-9 carry-forward acceptance, the missing-target SKIP contract and
the HTTP-500→ERROR matrix over ALL ten OUT drivers. The CAP-OUT-03/04
tests live in ``test_out_kb_detail.py``, the CAP-OUT-05..10 tests in
``test_out_direction_surfaces.py``; shared fixtures in
``out_direction_helpers.py``. The boundary pin: all ten OUT ``DRIVERS``
entries are real classes whose names match the registry ``driver_name``
with zero placeholders — IN-9 + OUT-10 are done, the 7 CHK entries
remain placeholders until Task 10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from benchmark.capabilities import CAPABILITIES, capability
from benchmark.drivers import DRIVERS, PlaceholderDriver
from benchmark.drivers.base import CapabilityStatus
from benchmark.drivers.out_direction import (
    AUTOCOMPLETE_LIMIT,
    OUT_DIRECTION_DRIVERS,
    PAGE_SIZE,
    EntityDetailDriver,
    EntryBrowseDriver,
    EntrySearchDriver,
)
from benchmark.drivers.out_records import (
    AutocompleteHit,
    EntryBrowseRecord,
    EntrySummary,
    SearchRecord,
)
from benchmark.tests.client_helpers import RecordedCall, ScriptedApi, make_client
from benchmark.tests.out_direction_helpers import (
    AUTOCOMPLETE_BODY,
    KB_AUTOCOMPLETE,
    KB_ENTRIES,
    KB_SEARCH,
    LIST_PAGE_ONE,
    LIST_PAGE_TWO,
    LIST_SINGLE_PAGE,
    context,
    invoke,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from benchmark.drivers.base import CapabilityDriver


def cast_browse(parsed: object | None) -> EntryBrowseRecord | None:
    """Narrow a parsed payload for assertions (tests mirror driver typing)."""
    return parsed if isinstance(parsed, EntryBrowseRecord) else None


# ---------------------------------------------------------------------------
# Task-9 carry-forward acceptance: the 10 replaced entries are real, CHK waits
# ---------------------------------------------------------------------------


def test_t9_carry_forward_all_ten_replaced_and_names_pinned() -> None:
    assert len(OUT_DIRECTION_DRIVERS) == 10
    assert set(OUT_DIRECTION_DRIVERS) == {
        spec.cap_id for spec in CAPABILITIES if spec.direction == "out"
    }
    for cap_id, driver in OUT_DIRECTION_DRIVERS.items():
        spec = capability(cap_id)
        assert spec.direction == "out"
        assert spec.shape == "rest", f"{cap_id}: OUT is all-REST per the registry"
        assert DRIVERS[cap_id] is driver
        assert driver.__name__ == spec.driver_name
        assert driver is not PlaceholderDriver


def test_t9_carry_forward_check_entries_still_placeholder() -> None:
    remaining = [spec.cap_id for spec in CAPABILITIES if DRIVERS[spec.cap_id] is PlaceholderDriver]
    assert remaining == [spec.cap_id for spec in CAPABILITIES if spec.direction == "check"]
    assert len(remaining) == 7


# ---------------------------------------------------------------------------
# CAP-OUT-01 — EntryBrowseDriver: paginated listing + autocomplete
# ---------------------------------------------------------------------------


def test_browse_driver_lists_single_page_then_autocompletes() -> None:
    routes = {
        f"GET {KB_ENTRIES}": LIST_SINGLE_PAGE,
        f"GET {KB_AUTOCOMPLETE}": AUTOCOMPLETE_BODY,
    }

    api, events, parsed = invoke(EntryBrowseDriver, routes)

    assert api.paths() == [f"GET {KB_ENTRIES}", f"GET {KB_AUTOCOMPLETE}"]
    assert api.calls[0].params == {"page": "1", "page_size": str(PAGE_SIZE)}
    assert api.calls[1].params == {"q": "Benchmark", "limit": str(AUTOCOMPLETE_LIMIT)}
    assert isinstance(parsed, EntryBrowseRecord)
    assert parsed.total == 2
    assert parsed.pages_fetched == 1
    assert parsed.entries == (
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
    assert parsed.autocomplete == (
        AutocompleteHit(
            id="entry-9", name="Anna Meyer", entity_type="character", slug="anna-meyer"
        ),
    )
    assert [event.step for event in events] == [
        "CAP-OUT-01:browse-page-1",
        "CAP-OUT-01:autocomplete",
    ]


def test_browse_driver_pages_until_total_is_reached() -> None:
    api = ScriptedApi()
    pages = [LIST_PAGE_ONE, LIST_PAGE_TWO]

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        if f"{call.method} {call.path}" == f"GET {KB_ENTRIES}":
            body = pages.pop(0)
            return httpx.Response(200, json=body)
        if f"{call.method} {call.path}" == f"GET {KB_AUTOCOMPLETE}":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected call: {call.method} {call.path}")

    api.respond_with(responder)

    result = EntryBrowseDriver().invoke(context(make_client(api, access_token="acc-1")))

    assert result.status is CapabilityStatus.OK, result.reason
    parsed = cast_browse(result.parsed)
    assert api.calls[0].params == {"page": "1", "page_size": str(PAGE_SIZE)}
    assert api.calls[1].params == {"page": "2", "page_size": str(PAGE_SIZE)}
    assert parsed is not None and parsed.pages_fetched == 2
    assert parsed.total == 101
    assert [entry.id for entry in parsed.entries][:2] == ["entry-9", "entry-2"]
    assert parsed.entries[-1].id == "entry-3"
    assert len(parsed.entries) == 101


# ---------------------------------------------------------------------------
# CAP-OUT-02 — EntrySearchDriver: lexical search over the reference probe
# ---------------------------------------------------------------------------


def test_search_driver_queries_probe_and_parses_pages() -> None:
    routes = {f"GET {KB_SEARCH}": LIST_SINGLE_PAGE}

    api, events, parsed = invoke(EntrySearchDriver, routes)

    assert api.paths() == [f"GET {KB_SEARCH}"]
    assert api.calls[0].params == {
        "q": "Benchmark",
        "page": "1",
        "page_size": str(PAGE_SIZE),
    }
    assert isinstance(parsed, SearchRecord)
    assert parsed.query == "Benchmark"
    assert parsed.total == 2
    assert parsed.pages_fetched == 1
    assert [entry.name for entry in parsed.entries] == ["Benchmark Figur", "HafenCity"]
    assert [event.step for event in events] == ["CAP-OUT-02:search-page-1"]


def test_search_driver_pages_until_total_is_reached() -> None:
    api = ScriptedApi()
    pages = [LIST_PAGE_ONE, LIST_PAGE_TWO]

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        assert f"{call.method} {call.path}" == f"GET {KB_SEARCH}"
        return httpx.Response(200, json=pages.pop(0))

    api.respond_with(responder)

    result = EntrySearchDriver().invoke(context(make_client(api, access_token="acc-1")))

    assert result.status is CapabilityStatus.OK, result.reason
    assert isinstance(result.parsed, SearchRecord)
    assert result.parsed.pages_fetched == 2
    assert result.parsed.total == 101
    assert api.calls[1].params == {
        "q": "Benchmark",
        "page": "2",
        "page_size": str(PAGE_SIZE),
    }


# ---------------------------------------------------------------------------
# Structural targets — missing ingest-discovered ids are SKIPPED, not made up
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("driver", "required_key"),
    [
        (EntityDetailDriver, "entry_id"),
    ],
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
# Error paths — HTTP 500 becomes ERROR with a reason, for every OUT driver
# ---------------------------------------------------------------------------


def _all_ten() -> tuple[tuple[Callable[[], CapabilityDriver], str, dict[str, str]], ...]:
    from benchmark.drivers.out_direction import GraphDriver
    from benchmark.drivers.out_direction_assist import (
        ProactiveSuggestionsDriver,
        ReferenceResolutionDriver,
        TemplatesDriver,
    )
    from benchmark.drivers.out_direction_surfaces import (
        SeriesCanonReadDriver,
        TimelineReadDriver,
        WikiReadDriver,
    )

    return (
        (EntryBrowseDriver, "CAP-OUT-01", {}),
        (EntrySearchDriver, "CAP-OUT-02", {}),
        (EntityDetailDriver, "CAP-OUT-03", {"entry_id": "entry-9"}),
        (GraphDriver, "CAP-OUT-04", {}),
        (SeriesCanonReadDriver, "CAP-OUT-05", {"series_id": "series-1"}),
        (WikiReadDriver, "CAP-OUT-06", {}),
        (TimelineReadDriver, "CAP-OUT-07", {}),
        (ProactiveSuggestionsDriver, "CAP-OUT-08", {"chapter_id": "chapter-1"}),
        (ReferenceResolutionDriver, "CAP-OUT-09", {}),
        (TemplatesDriver, "CAP-OUT-10", {}),
    )


_ALL_TEN = _all_ten()


@pytest.mark.parametrize(
    ("driver", "cap_id", "targets"),
    _ALL_TEN,
    ids=[cap_id for _driver, cap_id, _targets in _ALL_TEN],
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
