"""Direction-``out`` registry entries (CAP-OUT-01..CAP-OUT-10), literal.

RULE-04 split (plan Task 13 fix, ADR-085 P6): verbatim move from
``benchmark.capabilities_registry`` — identity, field values, and
inventory order unchanged; the holding-honest contract (set-equality
against ``benchmark/inventory/02-out.md``) lives in the registry module
and ``test_capabilities.py``.
"""

from __future__ import annotations

from typing import Final

from benchmark._registry_schema import CapabilitySpec, EndpointSpec

CAP_OUT: Final[tuple[CapabilitySpec, ...]] = (
    CapabilitySpec(
        cap_id="CAP-OUT-01",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="EntryBrowseDriver",
        output_schema="paginated KBEntryListResponse + autocomplete name list (CAP-OUT-01)",
        endpoints=(
            EndpointSpec("GET", "/novels/{novel_id}/kb/entries"),
            EndpointSpec("GET", "/novels/{novel_id}/kb/entries/autocomplete"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-02",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="EntrySearchDriver",
        output_schema="KBEntryListResponse filtered by substring match (CAP-OUT-02)",
        endpoints=(EndpointSpec("GET", "/novels/{novel_id}/kb/entries/search"),),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-03",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="EntityDetailDriver",
        output_schema="entities+relations JSON (CAP-OUT-03)",
        endpoints=(
            EndpointSpec("GET", "/novels/{novel_id}/kb/entries/{entry_id}"),
            EndpointSpec("GET", "/novels/{novel_id}/kb/entries/{entry_id}/relationships"),
            EndpointSpec("GET", "/novels/{novel_id}/kb/relationships/inverse-suggestion"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-04",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="GraphDriver",
        output_schema="GraphResponse (nodes/edges/statistics) + ShortestPathResponse (CAP-OUT-04)",
        endpoints=(
            EndpointSpec("GET", "/novels/{novel_id}/kb/graph"),
            EndpointSpec("GET", "/novels/{novel_id}/kb/graph/shortest-path"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-05",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="SeriesCanonReadDriver",
        output_schema="SeriesKBEntry list / single entry (CAP-OUT-05)",
        endpoints=(
            EndpointSpec("GET", "/series/{series_id}/kb"),
            EndpointSpec("GET", "/series/{series_id}/kb/{entry_id}"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-06",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="WikiReadDriver",
        output_schema="Wiki summary/chapter/index responses (overview + health) (CAP-OUT-06)",
        endpoints=(
            EndpointSpec("GET", "/novels/{novel_id}/wiki/summaries"),
            EndpointSpec("GET", "/novels/{novel_id}/wiki/summaries/{entity_id}"),
            EndpointSpec("GET", "/novels/{novel_id}/wiki/chapters/{chapter_id}/summary"),
            EndpointSpec("GET", "/novels/{novel_id}/wiki/index"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-07",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="TimelineReadDriver",
        output_schema="TimelineEventCRUDResponse list / single; CharacterAgeReport (CAP-OUT-07)",
        endpoints=(
            EndpointSpec("GET", "/planning/timeline/{novel_id}/events"),
            EndpointSpec("GET", "/planning/timeline/{novel_id}/events/{event_id}"),
            EndpointSpec("GET", "/planning/timeline/{novel_id}/character-ages"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-08",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="ProactiveSuggestionsDriver",
        output_schema="ranked KBSuggestionResponse list, max_results <= 100 (CAP-OUT-08)",
        endpoints=(EndpointSpec("GET", "/novels/{novel_id}/kb/suggestions/{chapter_id}"),),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-09",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="ReferenceResolutionDriver",
        output_schema="ResolveReferencesResponse (linked refs + rendered HTML) (CAP-OUT-09)",
        endpoints=(EndpointSpec("POST", "/novels/{novel_id}/kb/resolve-references"),),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-10",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="TemplatesDriver",
        output_schema="TemplateInfoResponse list / TemplateDetailResponse (CAP-OUT-10)",
        endpoints=(
            EndpointSpec("GET", "/novels/{novel_id}/kb/templates"),
            EndpointSpec("GET", "/novels/{novel_id}/kb/templates/{entity_type}"),
        ),
    ),
)
