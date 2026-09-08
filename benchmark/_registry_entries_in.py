"""Direction-``in`` registry entries (CAP-IN-01..CAP-IN-10), literal.

RULE-04 split (plan Task 13 fix, ADR-085 P6): verbatim move from
``benchmark.capabilities_registry`` — identity, field values, and
inventory order unchanged; the holding-honest contract (set-equality
against ``benchmark/inventory/01-in.md``) lives in the registry module
and ``test_capabilities.py``.
"""

from __future__ import annotations

from typing import Final

from benchmark._registry_schema import CapabilitySpec, EndpointSpec

CAP_IN: Final[tuple[CapabilitySpec, ...]] = (
    CapabilitySpec(
        cap_id="CAP-IN-01",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="ExtractionDriver",
        output_schema="extraction result JSON + apply response (updated KB entries) (CAP-IN-01)",
        endpoints=(
            EndpointSpec("POST", "/novels/{novel_id}/kb/extract/{chapter_id}"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/extract/apply"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-02",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="AssistSessionDriver",
        output_schema="session JSON with AI suggestions; complete returns entry ID (CAP-IN-02)",
        endpoints=(
            EndpointSpec("POST", "/novels/{novel_id}/kb/sessions"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/sessions/{session_id}/suggest/{field_key}"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/sessions/{session_id}/interview"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/sessions/{session_id}/enhance"),
            EndpointSpec("PATCH", "/novels/{novel_id}/kb/sessions/{session_id}/fields/{field_key}"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/sessions/{session_id}/complete"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-03",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="ImproveAnalysisDriver",
        output_schema="improvement suggestions + apply response (updated entry) (CAP-IN-03)",
        endpoints=(
            EndpointSpec("POST", "/novels/{novel_id}/kb/entities/{entry_id}/improve"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/entities/{entry_id}/improve/apply"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-04",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="WorldbuildingDriver",
        output_schema="analysis report + apply response with created KB relationships (CAP-IN-04)",
        endpoints=(
            EndpointSpec("POST", "/novels/{novel_id}/kb/worldbuilding/analyze"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/worldbuilding/apply"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-05",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="ManualAuthoringDriver",
        output_schema="created/updated KBEntry / SeriesKBEntry / KBRelationship (CAP-IN-05)",
        endpoints=(
            EndpointSpec("POST", "/novels/{novel_id}/kb/entries"),
            EndpointSpec("PATCH", "/novels/{novel_id}/kb/entries/{entry_id}"),
            EndpointSpec("POST", "/series/{series_id}/kb"),
            EndpointSpec("PATCH", "/series/{series_id}/kb/{entry_id}"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/relationships"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-06",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="ScopeMoveDriver",
        output_schema="scope-moved SeriesKBEntry/NovelKBEntry; JoinPreview/JoinResult (CAP-IN-06)",
        endpoints=(
            EndpointSpec("POST", "/novels/{novel_id}/kb/{entry_id}/promote"),
            EndpointSpec("POST", "/novels/{novel_id}/kb/{entry_id}/demote"),
            EndpointSpec("POST", "/series/{series_id}/novels"),
            EndpointSpec("POST", "/series/{series_id}/novels/{novel_id}/apply"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-07",
        direction="in",
        shape="sse",
        sse_flavor="A",
        driver_name="TimelineExtractionDriver",
        output_schema="SSE stream of extracted expressions; confirmed TimelineEvent (CAP-IN-07)",
        endpoints=(
            EndpointSpec("POST", "/planning/timeline/{novel_id}/extract"),
            EndpointSpec("POST", "/planning/timeline/{novel_id}/extract/confirm"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-08",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="WikiRefreshDriver",
        output_schema="WikiRefreshResponse (summary status); mark-stale affected count (CAP-IN-08)",
        endpoints=(
            EndpointSpec("POST", "/novels/{novel_id}/wiki/summaries/{entity_id}/refresh"),
            EndpointSpec("POST", "/novels/{novel_id}/wiki/mark-stale"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-09",
        direction="in",
        shape="sse",
        sse_flavor="B",
        driver_name="CharacterVoiceDriver",
        output_schema="SSE stream B: progress/result/done; voice analysis to KB (CAP-IN-09)",
        endpoints=(EndpointSpec("POST", "/analysis/character-voice/{novel_id}"),),
    ),
    CapabilitySpec(
        cap_id="CAP-IN-10",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="ResolutionDriver",
        output_schema="resolution analysis JSON (suggestions, stats); merge result (CAP-IN-10)",
        llm_backed=True,
        requires=("CAP-IN-01",),
        endpoints=(
            EndpointSpec("POST", "/novels/{novel_id}/kb/resolution/analyze"),
            EndpointSpec("GET", "/novels/{novel_id}/kb/resolution/suggestions"),
            EndpointSpec(
                "POST", "/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/endorse"
            ),
            EndpointSpec(
                "POST", "/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/reject"
            ),
        ),
    ),
)
