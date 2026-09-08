"""THE capability registry — all 27 inventoried entries, assembled.

RULE-04 split (plan Task 13 fix, ADR-085 P6): the direction entry tables
outgrew the 400-line hard limit and moved to
``benchmark._registry_entries_in`` / ``benchmark._registry_entries_out``;
the shared entry schema (type aliases + dataclasses) moved to
``benchmark._registry_schema`` (entry tables instantiate it at import
time, so one extra hop keeps table→schema acyclic). THIS module stays
the public import surface: every schema name, ``CAPABILITIES``,
``DRIVERS_PENDING``, and ``UNAVAILABLE_SURFACES`` remain importable from
here unchanged (``benchmark.capabilities`` re-exports to the wider
world; benchmark tests import ``DRIVERS_PENDING`` directly).

Held honest by ``test_capabilities.py`` against the inventory files
(set-equality, exactly 27 entries, directions, duplicate-freeness).

Per entry: ``cap_id``, ``direction`` (in/out/check), the invocation
``shape`` (rest/sse/poll, api-surface.md §7), the SSE ``sse_flavor``
(map §6, only on SSE shapes), the endpoint specs (method + path template
under ``/api/v1``, from the inventory's API path field / map §7), the
``output_schema`` — a ≤80-char pointer derived from the inventory's
``| Output artifact |`` field, citing the entry's own cap id — and the
``driver_name`` — the NAME of the driver class that plan Tasks 8-10
implement and map in ``benchmark/drivers``. All 27 entries are mounted
routes, so none carries ``unavailable_reason``. ``llm_backed`` records
honestly whether the driven path may call an LLM (``None`` = not
recorded for the pre-ADR-085 entries, where the inventory's tri-state
``LLM-backed`` row is the SSOT); ``requires`` lists ingest-precondition
cap ids a driver must satisfy first (ADR-085 P6, CAP-IN-10).

``DRIVERS_PENDING``: registry ids whose driver class is not mapped YET
(CAP-IN-10 only — plan Task 14 lands ``ResolutionDriver``).
``driver_for`` keeps raising ``DriverNotRegisteredError`` for them —
loud, never a silent no-op; the driver-completion pins subtract this
set until Task 14 empties it.

Unmounted surfaces (``UNAVAILABLE_SURFACES``): the retired KB-009
merge/dedup and CONS-001 chapter↔KB consistency are inventory FINDINGS
(register Findings 3 and 1), not entries — they have no CAP ids and are
therefore deliberately NOT in the entry table (that would break the
completeness test and invent ids). They are recorded here explicitly
with their 404-at-runtime reasons so the run artifacts can honestly list
them as ``SKIPPED(unavailable)`` — never silently omitted. KB-009 is
superseded by CAP-IN-10 (ADR-085 D5): the capability returned on the
mounted entity-resolution surface.
"""

from __future__ import annotations

from typing import Final

from benchmark._registry_entries_in import CAP_IN
from benchmark._registry_entries_out import CAP_OUT
from benchmark._registry_schema import (
    CapabilitySpec,
    Direction,
    EndpointSpec,
    InvocationShape,
    SseFlavor,
    UnavailableSurface,
)

__all__ = [
    "CAPABILITIES",
    "DRIVERS_PENDING",
    "UNAVAILABLE_SURFACES",
    "CapabilitySpec",
    "Direction",
    "EndpointSpec",
    "InvocationShape",
    "SseFlavor",
    "UnavailableSurface",
]

_CAP_CHK: Final[tuple[CapabilitySpec, ...]] = (
    CapabilitySpec(
        cap_id="CAP-CHK-01",
        direction="check",
        shape="rest",
        sse_flavor=None,
        driver_name="ConsistencyCheckDriver",
        output_schema="ConsistencyCheckResponse (combined contradiction report) (CAP-CHK-01)",
        endpoints=(EndpointSpec("POST", "/novels/{novel_id}/kb/consistency-check"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-02",
        direction="check",
        shape="rest",
        sse_flavor=None,
        driver_name="SeriesConsistencyDriver",
        output_schema="SeriesConsistencyCheckResponse + persisted drift snapshot GET (CAP-CHK-02)",
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
        output_schema="AuthorVoiceDriftResponse (trend + jumps + verdict, persisted) (CAP-CHK-03)",
        endpoints=(EndpointSpec("POST", "/series/{series_id}/voice-drift/check"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-04",
        direction="check",
        shape="rest",
        sse_flavor=None,
        driver_name="TemporalConsistencyDriver",
        output_schema="TemporalConsistencyResponse (rule_id issues + severity) (CAP-CHK-04)",
        endpoints=(EndpointSpec("GET", "/planning/timeline/{novel_id}/consistency"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-05",
        direction="check",
        shape="sse",
        sse_flavor="B",
        driver_name="VoiceCheckDriver",
        output_schema="SSE stream B: progress, per-character verdict entries, done (CAP-CHK-05)",
        endpoints=(EndpointSpec("POST", "/analysis/voice-check/{chapter_id}"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-06",
        direction="check",
        shape="sse",
        sse_flavor="B",
        driver_name="VoiceDriftDriver",
        output_schema="SSE stream B: per-character drift results + no_profile events (CAP-CHK-06)",
        endpoints=(EndpointSpec("POST", "/analysis/voice-drift/{novel_id}"),),
    ),
    CapabilitySpec(
        cap_id="CAP-CHK-07",
        direction="check",
        shape="sse",
        sse_flavor="B",
        driver_name="AuthorVoiceDriftDriver",
        output_schema="SSE stream B: narrator drift result + graceful no_profile (CAP-CHK-07)",
        endpoints=(EndpointSpec("POST", "/analysis/author-voice-drift/{novel_id}"),),
    ),
)

CAPABILITIES: Final[tuple[CapabilitySpec, ...]] = (*CAP_IN, *CAP_OUT, *_CAP_CHK)
"""The 27 inventory entries, in inventory order (in / out / check)."""

DRIVERS_PENDING: Final[frozenset[str]] = frozenset({"CAP-IN-10"})
"""Registry ids whose driver class is not mapped YET (plan Task 14 lands
``ResolutionDriver`` in ``benchmark/drivers``). ``driver_for`` keeps
raising ``DriverNotRegisteredError`` for these ids — loud, never a
silent no-op; the driver-completion pins subtract this set until Task 14
empties it."""

UNAVAILABLE_SURFACES: Final[tuple[UnavailableSurface, ...]] = (
    UnavailableSurface(
        label="KB-009 merge/dedup",
        direction="in",
        endpoints=(EndpointSpec("POST", "/novels/{novel_id}/kb/merge"),),
        reason=(
            "router kb/router_merge.py was deleted (ADR-085 D5, plan "
            "Task 11) — POST /kb/merge returns 404 at runtime; superseded "
            "by CAP-IN-10 (inventory 01-in Finding 1, register Finding "
            "3); driven as SKIPPED(unavailable)"
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
