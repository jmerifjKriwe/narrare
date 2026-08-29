"""THE capability registry — all 26 inventoried entries as literal data.

Hand-curated literal table (plan Task 7 decision): deterministic and
reviewable, held honest by ``test_capabilities.py`` which parses the
``### CAP-...`` headings (and each entry's ``| Direction |`` row) out of
``benchmark/inventory/0{1,2,3}-*.md`` and asserts set-equality, exactly
26 entries, matching directions, and duplicate-freeness.

Per entry: ``cap_id``, ``direction`` (in/out/check), the invocation
``shape`` (rest/sse/poll, api-surface.md §7), the SSE ``sse_flavor``
(map §6, only on SSE shapes), the endpoint specs (method + path template
under ``/api/v1``, from the inventory's API path field / map §7), and the
``driver_name`` — the NAME of the driver class that plan Tasks 8-10
implement and map in ``benchmark/drivers``. All 26 entries are mounted
routes, so none carries ``unavailable_reason``.

Unmounted surfaces (``UNAVAILABLE_SURFACES``): KB-009 merge/dedup and
CONS-001 chapter↔KB consistency are inventory FINDINGS (register
Findings 3 and 1), not entries — they have no CAP ids and are therefore
deliberately NOT in the 26-entry table (that would break the
completeness test and invent ids). They are recorded here explicitly
with their 404-at-runtime reasons so the run artifacts can honestly list
them as ``SKIPPED(unavailable)`` — never silently omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

Direction = Literal["in", "out", "check"]
InvocationShape = Literal["rest", "sse", "poll"]
SseFlavor = Literal["A", "B"]


@dataclass(frozen=True)
class EndpointSpec:
    """One method-pinned endpoint (path template relative to ``/api/v1``)."""

    method: str
    path: str


@dataclass(frozen=True)
class CapabilitySpec:
    """One inventoried capability: identity, shape, endpoints, driver ref."""

    cap_id: str
    direction: Direction
    shape: InvocationShape
    sse_flavor: SseFlavor | None
    driver_name: str
    endpoints: tuple[EndpointSpec, ...]
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class UnavailableSurface:
    """An inventoried capability whose routes 404 at runtime (unmounted)."""

    label: str
    direction: Direction
    endpoints: tuple[EndpointSpec, ...]
    reason: str


class UnknownCapabilityError(LookupError):
    """No registry entry exists for a capability id."""


_CAP_IN: Final[tuple[CapabilitySpec, ...]] = (
    CapabilitySpec(
        cap_id="CAP-IN-01",
        direction="in",
        shape="rest",
        sse_flavor=None,
        driver_name="ExtractionDriver",
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
        endpoints=(EndpointSpec("POST", "/analysis/character-voice/{novel_id}"),),
    ),
)

_CAP_OUT: Final[tuple[CapabilitySpec, ...]] = (
    CapabilitySpec(
        cap_id="CAP-OUT-01",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="EntryBrowseDriver",
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
        endpoints=(EndpointSpec("GET", "/novels/{novel_id}/kb/entries/search"),),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-03",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="EntityDetailDriver",
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
        endpoints=(EndpointSpec("GET", "/novels/{novel_id}/kb/suggestions/{chapter_id}"),),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-09",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="ReferenceResolutionDriver",
        endpoints=(EndpointSpec("POST", "/novels/{novel_id}/kb/resolve-references"),),
    ),
    CapabilitySpec(
        cap_id="CAP-OUT-10",
        direction="out",
        shape="rest",
        sse_flavor=None,
        driver_name="TemplatesDriver",
        endpoints=(
            EndpointSpec("GET", "/novels/{novel_id}/kb/templates"),
            EndpointSpec("GET", "/novels/{novel_id}/kb/templates/{entity_type}"),
        ),
    ),
)

_CAP_CHK: Final[tuple[CapabilitySpec, ...]] = (
    CapabilitySpec(
        cap_id="CAP-CHK-01",
        direction="check",
        shape="rest",
        sse_flavor=None,
        driver_name="ConsistencyCheckDriver",
        endpoints=(EndpointSpec("POST", "/novels/{novel_id}/kb/consistency-check"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-02",
        direction="check",
        shape="rest",
        sse_flavor=None,
        driver_name="SeriesConsistencyDriver",
        endpoints=(
            EndpointSpec("POST", "/series/{series_id}/consistency/check"),
            EndpointSpec("GET", "/series/{series_id}/consistency/{novel_id}"),
        ),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-03",
        direction="check",
        shape="rest",
        sse_flavor=None,
        driver_name="SeriesVoiceDriftDriver",
        endpoints=(EndpointSpec("POST", "/series/{series_id}/voice-drift/check"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-04",
        direction="check",
        shape="rest",
        sse_flavor=None,
        driver_name="TemporalConsistencyDriver",
        endpoints=(EndpointSpec("GET", "/planning/timeline/{novel_id}/consistency"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-05",
        direction="check",
        shape="sse",
        sse_flavor="B",
        driver_name="VoiceCheckDriver",
        endpoints=(EndpointSpec("POST", "/analysis/voice-check/{chapter_id}"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-06",
        direction="check",
        shape="sse",
        sse_flavor="B",
        driver_name="VoiceDriftDriver",
        endpoints=(EndpointSpec("POST", "/analysis/voice-drift/{novel_id}"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-07",
        direction="check",
        shape="sse",
        sse_flavor="B",
        driver_name="AuthorVoiceDriftDriver",
        endpoints=(EndpointSpec("POST", "/analysis/author-voice-drift/{novel_id}"),),
    ),
)

CAPABILITIES: Final[tuple[CapabilitySpec, ...]] = (*_CAP_IN, *_CAP_OUT, *_CAP_CHK)
"""The 26 inventory entries, in inventory order (in / out / check)."""

UNAVAILABLE_SURFACES: Final[tuple[UnavailableSurface, ...]] = (
    UnavailableSurface(
        label="KB-009 merge/dedup",
        direction="in",
        endpoints=(EndpointSpec("POST", "/novels/{novel_id}/kb/merge"),),
        reason=(
            "router kb/router_merge.py is never included in _app/main.py — "
            "POST /kb/merge returns 404 at runtime (inventory 01-in Finding 1, "
            "register Finding 3); driven as SKIPPED(unavailable)"
        ),
    ),
    UnavailableSurface(
        label="CONS-001 chapter-to-KB consistency",
        direction="check",
        endpoints=(
            EndpointSpec("POST", "/consistency/check"),
            EndpointSpec("POST", "/consistency/check/stream"),
            EndpointSpec("POST", "/consistency/chapters/{chapter_id}/check"),
        ),
        reason=(
            "router consistency/router.py is never included in _app/main.py — "
            "all /consistency routes return 404 at runtime (inventory 03-check "
            "Finding 1, register Finding 1); driven as SKIPPED(unavailable)"
        ),
    ),
)


def capability(cap_id: str) -> CapabilitySpec:
    """Look up one registry entry; unknown ids raise a precise error."""
    for spec in CAPABILITIES:
        if spec.cap_id == cap_id:
            return spec
    raise UnknownCapabilityError(
        f"unknown capability id {cap_id!r} (registry holds {len(CAPABILITIES)} entries)"
    )
