"""Seven-Point Story Structure adapter.

Dan Wells' 7-point structure:
  Hook → Plot Turn 1 → Pinch 1 → Midpoint → Pinch 2 → Plot Turn 2 → Resolution

Auto-registers with the module-level registry on import.
"""

from __future__ import annotations

from narrare_core.planning.adapters.base import (
    BeatDef,
    StageDef,
    StructureAdapterRegistry,
)


class SevenPointAdapter:
    """Seven-Point story structure."""

    def __init__(self) -> None:
        self._stages: list[StageDef] = [
            StageDef(
                id="hook",
                name="Hook",
                description="The starting state — establish the protagonist and stakes.",
                position=1,
                expected_beat_count=1,
            ),
            StageDef(
                id="plot-turn-1",
                name="Plot Turn 1",
                description="The first turning point that launches the story.",
                position=2,
                expected_beat_count=1,
            ),
            StageDef(
                id="pinch-1",
                name="Pinch 1",
                description="Pressure from the antagonist forces the protagonist to act.",
                position=3,
                expected_beat_count=1,
            ),
            StageDef(
                id="midpoint",
                name="Midpoint",
                description="The protagonist shifts from reaction to proactive action.",
                position=4,
                expected_beat_count=1,
            ),
            StageDef(
                id="pinch-2",
                name="Pinch 2",
                description="More pressure — the situation looks dire.",
                position=5,
                expected_beat_count=1,
            ),
            StageDef(
                id="plot-turn-2",
                name="Plot Turn 2",
                description="The crucial discovery or decision that leads to resolution.",
                position=6,
                expected_beat_count=1,
            ),
            StageDef(
                id="resolution",
                name="Resolution",
                description="The conflict is resolved; the protagonist has changed.",
                position=7,
                expected_beat_count=1,
            ),
        ]

        self._stage_ids: set[str] = {s.id for s in self._stages}

        self._beats: dict[str, list[BeatDef]] = {
            "hook": [
                BeatDef(
                    "The Hook", "Establish the starting state and the gap to the ending.", True
                ),
            ],
            "plot-turn-1": [
                BeatDef(
                    "First Turning Point", "An event disrupts the status quo irreversibly.", True
                ),
            ],
            "pinch-1": [
                BeatDef("Pinching Pressure", "Antagonistic forces apply pressure.", True),
            ],
            "midpoint": [
                BeatDef(
                    "The Midpoint Shift", "The protagonist moves from passive to active.", True
                ),
            ],
            "pinch-2": [
                BeatDef("Greater Pressure", "The stakes become personal and urgent.", True),
            ],
            "plot-turn-2": [
                BeatDef("Key Revelation", "The protagonist gains the final piece needed.", True),
            ],
            "resolution": [
                BeatDef("Climactic Resolution", "The hero applies everything learned.", True),
            ],
        }

    @property
    def structure_type(self) -> str:
        return "seven_point"

    @property
    def stages(self) -> list[StageDef]:
        return list(self._stages)

    def suggest_stage(self, chapter_number: int, total_chapters: int) -> str:
        if total_chapters <= 0:
            return "hook"
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
    registry.register(SevenPointAdapter())
