"""Deterministic evaluators for planning_structure evals.

Each evaluator is metadata-aware: it inspects the case's ``agent_type`` and
returns ``1.0`` (not applicable) for cases belonging to the other agents,
mirroring the behaviour of ``ReadabilitySchemaValidator``. When applicable,
it asserts REAL schema/range properties of the agent's output shape — no stubs.

Validated output schemas (file:symbol):

- OutlineAgent      → ``narrare_core.agents.outline_types.OutlineOutput``
- CharacterArcAgent → ``narrare_core.agents.character_arc_types.CharacterArcOutput``
- TimelineAgent     → ``narrare_core.agents.timeline_types.TimelineOutput``
- WorldbuildingAgent→ ``narrare_core.agents.worldbuilding_types.WorldbuildingPhase1Output``

Known value sets are sourced authoritatively from the agent type docstrings
and ``worldbuilding_validators.VALID_SEVERITIES``.

Reality-check note (architectural-discipline: documented != implemented):
the eval-expansion-plan prose lists OutlineAgent as testing "variant count
compliance", but the real ``OutlineOutput`` carries no variant concept — its
deterministic invariants (``OutlineAgent._validate_output``) are a non-empty
``chapter_title`` and at least one non-empty scene. The validator below
asserts the real schema, not the plan's prose. Validating a non-existent
"variant count" would be a stub.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import PlanningStructureResult

# ---------------------------------------------------------------------------
# Authoritative value sets (mirror the agents' own contracts).
# ---------------------------------------------------------------------------

# From character_arc_types.CharacterArcOutput.arc_type docstring
# ("growth, fall, transformation, flat").
_ARC_TYPES: frozenset[str] = frozenset({"growth", "fall", "transformation", "flat"})

# From worldbuilding_types.Phase1GapOutput.gap_type comment
# (missing_entity, missing_field, missing_connection, missing_body).
_GAP_TYPES: frozenset[str] = frozenset(
    {"missing_entity", "missing_field", "missing_connection", "missing_body"}
)

# From worldbuilding_validators.VALID_SEVERITIES (the project-wide
# worldbuilding severity vocabulary; Phase1GapOutput.severity defaults to
# "major" which is a member).
_WORLDBUILDING_SEVERITIES: frozenset[str] = frozenset({"critical", "major", "minor"})

# Sanity upper bounds — catch runaway/regressed outputs without
# over-constraining. (OutlineAgent has no documented scene cap; the agent
# invariant is only "at least one scene". These bounds exist purely to make
# a runaway regression visible.)
_OUTLINE_MAX_SCENES = 30
_TIMELINE_MAX_EVENTS = 60


def _score(checks: list[bool]) -> float:
    """Return the fraction of satisfied checks (0.0 when there are none)."""

    if not checks:
        return 0.0
    return sum(1 for ok in checks if ok) / len(checks)


def _chapter_number(value: str) -> int | None:
    """Return the first numeric chapter marker in *value*, if present."""

    match = re.search(r"\bchapter\s+(\d+)\b", value, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


@dataclass
class OutlineSchemaValidator(Evaluator[Any, PlanningStructureResult, dict[str, Any]]):
    """Validate scene structure and title invariants for OutlineAgent.

    Not applicable (returns 1.0) when the case ``agent_type`` is not ``outline``.
    When applicable, checks (mirrors ``OutlineAgent._validate_output``):

    - outline section present
    - chapter_title non-empty (agent invariant)
    - at least one non-empty scene (agent invariant)
    - every scene non-empty (agent filters empties)
    - scene count within the sanity upper bound
    - outline_text non-empty when scenes are present
    """

    def evaluate(
        self, ctx: EvaluatorContext[Any, PlanningStructureResult, dict[str, Any]]
    ) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "outline":
            return 1.0

        section = ctx.output.outline
        if section is None:
            return 0.0

        non_empty_scenes = [s for s in section.scenes if s.strip()]
        checks: list[bool] = [
            bool(section.chapter_title.strip()),
            bool(non_empty_scenes),
            all(s.strip() for s in section.scenes) if section.scenes else True,
            len(section.scenes) <= _OUTLINE_MAX_SCENES,
            bool(section.outline_text.strip()) if section.scenes else True,
        ]

        return _score(checks)


@dataclass
class CharacterArcSchemaValidator(Evaluator[Any, PlanningStructureResult, dict[str, Any]]):
    """Validate arc type, phase identification, and goal/state coherence for CharacterArcAgent.

    Not applicable (returns 1.0) when the case ``agent_type`` is not ``character_arc``.
    When applicable, checks (mirrors ``CharacterArcAgent._validate_output``):

    - character_arc section present
    - character_name non-empty (agent invariant)
    - starting_state non-empty (agent invariant — goal/state coherence)
    - ending_state non-empty (agent invariant — goal/state coherence)
    - arc_type in the known set {growth, fall, transformation, flat}
    - phases count in 3-5 when present (agent invariant)
    - every phase has non-empty phase_name and description (agent invariant)
    """

    def evaluate(
        self, ctx: EvaluatorContext[Any, PlanningStructureResult, dict[str, Any]]
    ) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "character_arc":
            return 1.0

        section = ctx.output.character_arc
        if section is None:
            return 0.0

        checks: list[bool] = [
            bool(section.character_name.strip()),
            bool(section.starting_state.strip()),
            bool(section.ending_state.strip()),
            section.arc_type in _ARC_TYPES,
            (3 <= len(section.phases) <= 5) if section.phases else True,
        ]
        for phase in section.phases:
            checks.append(bool(phase.phase_name.strip()))
            checks.append(bool(phase.description.strip()))

        return _score(checks)


@dataclass
class TimelineSchemaValidator(Evaluator[Any, PlanningStructureResult, dict[str, Any]]):
    """Validate temporal ordering, event-chapter linking, and event identity for TimelineAgent.

    Not applicable (returns 1.0) when the case ``agent_type`` is not ``timeline``.
    When applicable, checks (mirrors ``TimelineAgent._validate_output``):

    - timeline section present
    - overall_assessment non-empty
    - every event has non-empty event_name and description (agent invariant)
    - every event has non-empty chapter_reference (event-chapter linking)
    - every event has non-empty timestamp (temporal traceability)
    - numeric chapter markers are monotonic (temporal ordering)
    - numeric timestamp/chapter_reference markers agree (chapter-data consistency)
    - no duplicate (event_name, timestamp) pair (agent invariant)
    - event count within the sanity upper bound
    """

    def evaluate(
        self, ctx: EvaluatorContext[Any, PlanningStructureResult, dict[str, Any]]
    ) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "timeline":
            return 1.0

        section = ctx.output.timeline
        if section is None:
            return 0.0

        checks: list[bool] = [
            bool(section.overall_assessment.strip()),
            len(section.timeline_events) <= _TIMELINE_MAX_EVENTS,
        ]

        seen: set[tuple[str, str]] = set()
        ordered_chapters: list[int] = []
        for event in section.timeline_events:
            checks.append(bool(event.event_name.strip()))
            checks.append(bool(event.description.strip()))
            checks.append(bool(event.chapter_reference.strip()))
            checks.append(bool(event.timestamp.strip()))
            timestamp_chapter = _chapter_number(event.timestamp)
            reference_chapter = _chapter_number(event.chapter_reference)
            checks.append(
                timestamp_chapter is None
                or reference_chapter is None
                or timestamp_chapter == reference_chapter
            )
            chapter_number = (
                reference_chapter if reference_chapter is not None else timestamp_chapter
            )
            if chapter_number is not None:
                ordered_chapters.append(chapter_number)
            key = (event.event_name.strip(), event.timestamp.strip())
            checks.append(key not in seen)
            seen.add(key)

        if len(ordered_chapters) > 1:
            checks.append(ordered_chapters == sorted(ordered_chapters))

        return _score(checks)


@dataclass
class WorldbuildingSchemaValidator(Evaluator[Any, PlanningStructureResult, dict[str, Any]]):
    """Validate Phase 1 entity-schema output and structure conformance for WorldbuildingAgent.

    Not applicable (returns 1.0) when the case ``agent_type`` is not ``worldbuilding``.
    When applicable, checks (mirrors ``validate_worldbuilding_phase1``):

    - worldbuilding section present
    - assessment non-empty
    - worldbuilding_score in [0.0, 1.0] (schema-enforced; redundant safety net)
    - every gap has non-empty description and gap_type (Phase 1 invariant)
    - every gap_type in the known set
      {missing_entity, missing_field, missing_connection, missing_body}
    - every gap story_relevance in [0.0, 1.0] and severity in the known set
    - every connection has non-empty source/target ids and suggested_rel_type
    - every connection confidence and story_relevance in [0.0, 1.0]
    """

    def evaluate(
        self, ctx: EvaluatorContext[Any, PlanningStructureResult, dict[str, Any]]
    ) -> float:
        if not ctx.metadata or ctx.metadata.get("agent_type") != "worldbuilding":
            return 1.0

        section = ctx.output.worldbuilding
        if section is None:
            return 0.0

        checks: list[bool] = [
            bool(section.assessment.strip()),
            0.0 <= section.worldbuilding_score <= 1.0,
        ]

        for gap in section.gaps:
            checks.append(bool(gap.description.strip()))
            checks.append(bool(gap.gap_type.strip()))
            checks.append(gap.gap_type in _GAP_TYPES)
            checks.append(0.0 <= gap.story_relevance <= 1.0)
            checks.append(gap.severity in _WORLDBUILDING_SEVERITIES)

        for connection in section.connection_suggestions:
            checks.append(bool(connection.source_entity_id.strip()))
            checks.append(bool(connection.target_entity_id.strip()))
            checks.append(bool(connection.suggested_rel_type.strip()))
            checks.append(0.0 <= connection.confidence <= 1.0)
            checks.append(0.0 <= connection.story_relevance <= 1.0)

        return _score(checks)
