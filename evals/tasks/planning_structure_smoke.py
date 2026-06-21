"""Deterministic smoke task for the planning_structure eval suite.

Mirrors the ``analysis_metrics_smoke.py`` precedent: a standalone module with
the CI-safe task function and its producer helpers, imported lazily by
``SmokeTaskFactory.planning_structure_task`` so that ``evals/tasks/smoke.py``
stays within RULE-04 file-size limits.

Four planning-panel agents are covered (Outline, CharacterArc, Timeline,
Worldbuilding). Each producer derives a schema-valid result section from the
input prompt — no LLM is called. The output mirrors the real agent's output
shape so the metadata-aware evaluators assert genuine schema/range/count
properties.

Pure text-extraction helpers live in ``evals.tasks._planning_parsing`` so this
module stays compact and within the RULE-04 file-size limit.
"""

from __future__ import annotations

import re

from evals.models import (
    CharacterArcPhaseSection,
    CharacterArcSection,
    OutlineSection,
    PlanningStructureInput,
    PlanningStructureResult,
    TimelineEventSection,
    TimelineSection,
    WorldbuildingConnectionSection,
    WorldbuildingGapSection,
    WorldbuildingSection,
)
from evals.tasks._planning_parsing import (
    capitalized_tokens,
    detect_arc_type,
    event_name_from,
    extract_relationships,
    extract_state_pair,
    first_character_name,
    parse_entities,
    split_sentences,
)


async def planning_structure_task(inputs: object) -> object:
    """Run the CI-safe planning_structure smoke task."""

    return await planning_structure(PlanningStructureInput.model_validate(inputs))


async def planning_structure(inputs: PlanningStructureInput) -> PlanningStructureResult:
    """Produce deterministic, schema-valid planning output without LLM calls.

    Routes to a per-agent deterministic producer based on ``agent_type``.
    Each producer yields a result whose section matches the real agent's
    output shape and satisfies the metadata-aware validators (so smoke
    asserts REAL schema/range/count behaviour, not stubs).
    """

    if inputs.agent_type == "outline":
        return PlanningStructureResult(outline=_outline_smoke(inputs.prompt_text))
    if inputs.agent_type == "character_arc":
        return PlanningStructureResult(character_arc=_character_arc_smoke(inputs.prompt_text))
    if inputs.agent_type == "timeline":
        return PlanningStructureResult(timeline=_timeline_smoke(inputs.prompt_text))
    return PlanningStructureResult(worldbuilding=_worldbuilding_smoke(inputs.prompt_text))


# ---------------------------------------------------------------------------
# OutlineAgent
# ---------------------------------------------------------------------------


def _outline_smoke(prompt_text: str) -> OutlineSection:
    """Derive a chapter title and scene list from the brief.

    First line → chapter_title; remaining sentences → scenes. Falls back to a
    single deterministic scene so the agent's "at least one scene" invariant
    always holds.
    """

    lines = [ln.strip() for ln in prompt_text.splitlines() if ln.strip()]
    chapter_title = lines[0] if lines else "Untitled Chapter"
    body = " ".join(lines[1:]) if len(lines) > 1 else prompt_text

    sentences = split_sentences(body)
    if not sentences:
        # Fall back to the title itself as a single scene if nothing parses.
        sentences = (
            [chapter_title] if chapter_title.strip() else ["Opening scene (deterministic smoke)."]
        )

    return OutlineSection(
        chapter_title=chapter_title,
        scenes=sentences,
        outline_text="\n\n".join(sentences),
        metadata={"smoke": True},
    )


# ---------------------------------------------------------------------------
# CharacterArcAgent
# ---------------------------------------------------------------------------


# Deterministic phase templates (name, verb-phrase, emotion, turning point, chapters).
# Drives the 3-phase arc so the producer stays compact while still satisfying
# the agent's "3-5 phases, each non-empty" invariants.
_ARC_PHASES: list[tuple[str, str, str, str, str]] = [
    (
        "Inciting shift",
        "confronts the initial pressure of the arc.",
        "unsettled",
        "The catalyst event that begins the change.",
        "Chapters 1-4",
    ),
    (
        "Struggle",
        "resists or wrestles with the change.",
        "conflicted",
        "The midpoint reversal that raises the stakes.",
        "Chapters 5-9",
    ),
    (
        "Resolution",
        "settles into a new state.",
        "resolved",
        "The climactic decision that completes the arc.",
        "Chapters 10-14",
    ),
]


def _character_arc_smoke(prompt_text: str) -> CharacterArcSection:
    """Derive character name, start/end states, arc type, and 3-5 phases.

    Always emits 3 phases with non-empty names and descriptions so the
    agent's phase invariants hold.
    """

    character_name = first_character_name(prompt_text)
    starting_state, ending_state = extract_state_pair(prompt_text)
    arc_type = detect_arc_type(prompt_text)

    phases = [
        CharacterArcPhaseSection(
            phase_name=name,
            description=f"{character_name} {verb}",
            emotional_state=emotion,
            turning_point=turning,
            chapters_suggested=chapters,
        )
        for name, verb, emotion, turning, chapters in _ARC_PHASES
    ]
    resolution_desc = f"{character_name} settles into {ending_state or 'a new equilibrium'}."
    phases[-1] = phases[-1].model_copy(update={"description": resolution_desc})

    return CharacterArcSection(
        character_name=character_name,
        starting_state=starting_state,
        ending_state=ending_state,
        arc_type=arc_type,
        phases=phases,
        key_relationships=extract_relationships(prompt_text),
        internal_conflict=f"The tension between {character_name}'s starting and ending states.",
        resolution=f"{character_name} reconciles the arc through {arc_type}.",
        metadata={"smoke": True},
    )


# ---------------------------------------------------------------------------
# TimelineAgent
# ---------------------------------------------------------------------------


def _timeline_smoke(prompt_text: str) -> TimelineSection:
    """Parse ``Chapter N: ...`` segments into ordered events.

    Each segment becomes one event with a non-empty ``chapter_reference`` and
    ``timestamp``. If the text mentions "conflict"/"inconsistency", a
    temporal_conflict entry is emitted. Guarantees at least one event.
    """

    events = _parse_chapter_events(prompt_text)
    conflicts: list[str] = []
    lowered = prompt_text.lower()
    if "conflict" in lowered or "inconsisten" in lowered:
        conflicts.append(
            "Possible temporal conflict flagged in the source brief (deterministic smoke)."
        )

    assessment = (
        f"Smoke timeline: {len(events)} event(s) ordered across chapters. "
        "Deterministic — no model called."
    )

    return TimelineSection(
        timeline_events=events,
        temporal_conflicts=conflicts,
        coverage_gaps=[],
        overall_assessment=assessment,
        metadata={"smoke": True},
    )


def _parse_chapter_events(text: str) -> list[TimelineEventSection]:
    """Turn ``Chapter N: rest`` segments into timeline events."""

    matches = list(
        re.finditer(r"Chapter\s+(\d+)\s*:\s*(.+?)(?=Chapter\s+\d+\s*:|$)", text, flags=re.DOTALL)
    )
    events: list[TimelineEventSection] = []
    for match in matches:
        chapter_num = match.group(1)
        body = match.group(2).strip()
        sentences = split_sentences(body)
        summary = sentences[0] if sentences else (body or f"Events of chapter {chapter_num}.")
        events.append(
            TimelineEventSection(
                event_name=event_name_from(summary),
                description=summary,
                timestamp=f"Chapter {chapter_num}",
                chapter_reference=f"Chapter {chapter_num}",
                characters_involved=capitalized_tokens(body),
            )
        )

    if not events:
        # Edge case: no "Chapter N:" markers — emit a single fallback event so
        # the agent's non-empty invariants still hold.
        sentence = split_sentences(text)
        summary = sentence[0] if sentence else "Fallback timeline event (deterministic smoke)."
        events.append(
            TimelineEventSection(
                event_name=event_name_from(summary),
                description=summary,
                timestamp="Chapter 1",
                chapter_reference="Chapter 1",
                characters_involved=capitalized_tokens(text),
            )
        )
    return events


# ---------------------------------------------------------------------------
# WorldbuildingAgent (Phase 1)
# ---------------------------------------------------------------------------


def _worldbuilding_smoke(prompt_text: str) -> WorldbuildingSection:
    """Parse ``Type: Name`` entities into Phase 1 gaps and connections.

    With two or more entities, emits one connection suggestion and a
    ``missing_connection`` gap to exercise both output lists. With any
    entities, emits a ``missing_field`` gap. Guarantees all float fields stay
    within [0, 1] and gap_type/severity within the known sets.
    """

    entities = parse_entities(prompt_text)

    gaps: list[WorldbuildingGapSection] = []
    connections: list[WorldbuildingConnectionSection] = []
    candidate_pairs: list[tuple[str, str]] = []

    if len(entities) >= 2:
        first, second = entities[0], entities[1]
        connections.append(_connection(first, second))
        candidate_pairs.append((first["id"], second["id"]))
        gaps.append(
            _gap(
                first,
                "missing_connection",
                f"{first['name']} has no documented link to {second['name']}.",
                severity="major",
                related_type=second["type"],
                story_relevance=0.6,
            )
        )

    if entities:
        sparse = entities[0]
        gaps.append(
            _gap(
                sparse,
                "missing_field",
                f"{sparse['name']} is missing template field 'description' (deterministic smoke).",
                severity="minor",
                field_key="description",
                story_relevance=0.4,
            )
        )

    score = max(0.0, min(1.0, 1.0 - 0.15 * len(gaps)))
    assessment = (
        f"Smoke worldbuilding: {len(gaps)} gap(s) and {len(connections)} connection(s). "
        "Deterministic — no model called."
    )

    return WorldbuildingSection(
        gaps=gaps,
        connection_suggestions=connections,
        assessment=assessment,
        worldbuilding_score=score,
        candidate_pairs_for_consistency=candidate_pairs,
    )


def _connection(first: dict[str, str], second: dict[str, str]) -> WorldbuildingConnectionSection:
    """Build a deterministic connection suggestion between two entities."""

    return WorldbuildingConnectionSection(
        source_entity_id=first["id"],
        source_entity_name=first["name"],
        target_entity_id=second["id"],
        target_entity_name=second["name"],
        suggested_rel_type="related_to",
        inverse_rel_type="related_to",
        reasoning=(
            "Two entities share the story world without an explicit link (deterministic smoke)."
        ),
        confidence=0.7,
        story_relevance=0.6,
    )


def _gap(
    entity: dict[str, str],
    gap_type: str,
    description: str,
    *,
    severity: str,
    story_relevance: float,
    field_key: str | None = None,
    related_type: str | None = None,
) -> WorldbuildingGapSection:
    """Build a deterministic Phase 1 gap finding for *entity*."""

    return WorldbuildingGapSection(
        entity_id=entity["id"],
        entity_name=entity["name"],
        entity_type=entity["type"],
        gap_type=gap_type,
        field_key=field_key,
        description=description,
        related_entity_type=related_type,
        story_relevance=story_relevance,
        severity=severity,
    )
