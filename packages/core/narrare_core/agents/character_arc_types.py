"""Output types for CharacterArcAgent.

See ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ArcPhase(BaseModel):
    """A single phase in a character's development arc.

    Attributes:
        phase_name: Short name for this phase.
        description: What happens during this phase.
        emotional_state: The character's emotional state throughout this phase.
        turning_point: The key event that triggers this phase.
        chapters_suggested: Suggested chapter range for this phase.
    """

    phase_name: str = ""
    description: str = ""
    emotional_state: str = ""
    turning_point: str = ""
    chapters_suggested: str = ""


class CharacterArcOutput(BaseModel):
    """Structured output of a CharacterArcAgent run.

    Attributes:
        character_name: Name of the character.
        starting_state: Description of the character's state at the beginning.
        ending_state: Description of the character's state at the end.
        arc_type: Type of arc (growth, fall, transformation, flat).
        phases: List of arc phases (3-5 phases).
        key_relationships: Relationships that influence or are affected by the arc.
        internal_conflict: The character's internal or psychological struggle.
        resolution: How the internal conflict resolves.
        metadata: Additional metadata (model info, tokens, etc.).
    """

    character_name: str = ""
    starting_state: str = ""
    ending_state: str = ""
    arc_type: str = ""
    phases: list[ArcPhase] = []
    key_relationships: list[str] = []
    internal_conflict: str = ""
    resolution: str = ""
    metadata: dict[str, Any] = {}
