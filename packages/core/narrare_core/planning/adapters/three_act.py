"""Three-Act Structure adapter.

Classic 3-act dramatic structure:
  Act I  — Setup (25%)
  Act II — Confrontation (50%)
  Act III — Resolution (25%)

Auto-registers with the module-level registry on import.
"""

from __future__ import annotations

from narrare_core.planning.adapters.base import (
    BeatDef,
    StageDef,
    StructureAdapterRegistry,
)


class ThreeActAdapter:
    """Three-Act story structure."""

    def __init__(self) -> None:
        self._stages: list[StageDef] = [
            StageDef(
                id="act-1",
                name="Act I: Setup",
                description=(
                    "Establish the world, introduce characters, and present "
                    "the inciting incident that launches the story."
                ),
                position=1,
                expected_beat_count=3,
            ),
            StageDef(
                id="act-2",
                name="Act II: Confrontation",
                description=(
                    "The protagonist faces obstacles, allies and enemies emerge, "
                    "stakes rise through a midpoint reversal."
                ),
                position=2,
                expected_beat_count=4,
            ),
            StageDef(
                id="act-3",
                name="Act III: Resolution",
                description=(
                    "The climax brings the central conflict to a head, followed "
                    "by resolution and a new equilibrium."
                ),
                position=3,
                expected_beat_count=2,
            ),
        ]

        self._beats: dict[str, list[BeatDef]] = {
            "act-1": [
                BeatDef(
                    title="Opening / Status Quo",
                    description="Establish the everyday world and protagonist's normal life.",
                    required=True,
                ),
                BeatDef(
                    title="Inciting Incident",
                    description="An event disrupts the status quo and sets the story in motion.",
                    required=True,
                ),
                BeatDef(
                    title="Setup Elements",
                    description="Introduce key characters, relationships, and world rules.",
                    required=False,
                ),
            ],
            "act-2": [
                BeatDef(
                    title="Rising Action",
                    description="Obstacles intensify; the protagonist pursues the goal.",
                    required=True,
                ),
                BeatDef(
                    title="Midpoint",
                    description="A twist or revelation that raises stakes and shifts direction.",
                    required=True,
                ),
                BeatDef(
                    title="Complications",
                    description="New challenges and setbacks test the protagonist's resolve.",
                    required=False,
                ),
                BeatDef(
                    title="All Is Lost Moment",
                    description="The lowest point — the goal seems unreachable.",
                    required=False,
                ),
            ],
            "act-3": [
                BeatDef(
                    title="Climax",
                    description="The decisive confrontation or turning point of the story.",
                    required=True,
                ),
                BeatDef(
                    title="Resolution",
                    description="Loose ends are tied up; the new normal is established.",
                    required=True,
                ),
            ],
        }

    @property
    def structure_type(self) -> str:
        return "three_act"

    @property
    def stages(self) -> list[StageDef]:
        return list(self._stages)

    def suggest_stage(self, chapter_number: int, total_chapters: int) -> str:
        if total_chapters <= 0:
            return "act-1"
        ratio = chapter_number / total_chapters
        if ratio <= 1 / 3:
            return "act-1"
        if ratio <= 2 / 3:
            return "act-2"
        return "act-3"

    def validate_assignment(self, stage_id: str, chapter_number: int) -> bool:
        return stage_id in {"act-1", "act-2", "act-3"}

    def get_beat_expectations(self, stage_id: str) -> list[BeatDef]:
        return list(self._beats.get(stage_id, []))


def register(registry: StructureAdapterRegistry) -> None:
    """Module-level hook called by adapters/__init__.py during import."""
    registry.register(ThreeActAdapter())
