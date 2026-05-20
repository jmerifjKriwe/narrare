"""Five-Act Structure adapter.

Classic 5-act dramatic structure (Freytag's Pyramid):
  Exposition → Rising Action → Climax → Falling Action → Resolution

Each act occupies roughly 20% of the narrative.

Auto-registers with the module-level registry on import.
"""

from __future__ import annotations

from narrare_core.planning.adapters.base import (
    BeatDef,
    StageDef,
    StructureAdapterRegistry,
)


class FiveActAdapter:
    """Five-Act story structure."""

    def __init__(self) -> None:
        self._stages: list[StageDef] = [
            StageDef(
                id="exposition",
                name="Exposition",
                description="Introduce characters, setting, and the initial situation.",
                position=1,
                expected_beat_count=2,
            ),
            StageDef(
                id="rising-action",
                name="Rising Action",
                description="Tension builds through a series of complications and conflicts.",
                position=2,
                expected_beat_count=3,
            ),
            StageDef(
                id="climax",
                name="Climax",
                description="The turning point — the moment of greatest tension.",
                position=3,
                expected_beat_count=2,
            ),
            StageDef(
                id="falling-action",
                name="Falling Action",
                description="Consequences of the climax unfold; tension decreases.",
                position=4,
                expected_beat_count=2,
            ),
            StageDef(
                id="resolution",
                name="Resolution",
                description="Conflicts are resolved; the story reaches its conclusion.",
                position=5,
                expected_beat_count=2,
            ),
        ]

        self._stage_ids: set[str] = {s.id for s in self._stages}

        self._beats: dict[str, list[BeatDef]] = {
            "exposition": [
                BeatDef(
                    title="World Introduction",
                    description="Establish setting, time period, and social context.",
                    required=True,
                ),
                BeatDef(
                    title="Character Introduction",
                    description="Introduce the protagonist and key supporting characters.",
                    required=True,
                ),
            ],
            "rising-action": [
                BeatDef(
                    title="Inciting Incident",
                    description="The event that sets the main conflict in motion.",
                    required=True,
                ),
                BeatDef(
                    title="Complications",
                    description="Obstacles and challenges that escalate the conflict.",
                    required=False,
                ),
                BeatDef(
                    title="Point of No Return",
                    description="The protagonist commits irrevocably to the journey.",
                    required=True,
                ),
            ],
            "climax": [
                BeatDef(
                    title="Peak Confrontation",
                    description="The decisive moment where the central conflict peaks.",
                    required=True,
                ),
                BeatDef(
                    title="Revelation",
                    description="A key truth or realization emerges during the climax.",
                    required=False,
                ),
            ],
            "falling-action": [
                BeatDef(
                    title="Aftermath",
                    description="Immediate consequences of the climax unfold.",
                    required=True,
                ),
                BeatDef(
                    title="Loose Threads",
                    description="Subplots and secondary conflicts are addressed.",
                    required=False,
                ),
            ],
            "resolution": [
                BeatDef(
                    title="New Equilibrium",
                    description="The world settles into a new normal after the conflict.",
                    required=True,
                ),
                BeatDef(
                    title="Closing Image",
                    description="A final scene or image that echoes the story's theme.",
                    required=False,
                ),
            ],
        }

    @property
    def structure_type(self) -> str:
        return "five_act"

    @property
    def stages(self) -> list[StageDef]:
        return list(self._stages)

    def suggest_stage(self, chapter_number: int, total_chapters: int) -> str:
        if total_chapters <= 0:
            return "exposition"
        count = len(self._stages)
        # Use (chapter_number - 1) so chapter 1 maps to first stage
        idx = min(int(((chapter_number - 1) / total_chapters) * count), count - 1)
        return self._stages[idx].id

    def validate_assignment(self, stage_id: str, chapter_number: int) -> bool:
        return stage_id in self._stage_ids

    def get_beat_expectations(self, stage_id: str) -> list[BeatDef]:
        return list(self._beats.get(stage_id, []))


def register(registry: StructureAdapterRegistry) -> None:
    """Module-level hook called by adapters/__init__.py during import."""
    registry.register(FiveActAdapter())
