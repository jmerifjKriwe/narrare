"""Hero's Journey Structure adapter.

Campbell's 12-stage monomyth, condensed for practical visual layout.
When chapters are few, stages collapse into three groups:
  Beginning (ordinary-world … crossing-threshold),
  Middle (tests … ordeal),
  End (reward … return-with-elixir).

Auto-registers with the module-level registry on import.
"""

from __future__ import annotations

from narrare_core.planning.adapters.base import (
    BeatDef,
    StageDef,
    StructureAdapterRegistry,
)

# Collapsed groups for when chapters < stages
_BEGIN = {"ordinary-world", "call-to-adventure", "refusal", "mentor", "crossing-threshold"}
_MIDDLE = {"tests-allies-enemies", "approach", "ordeal"}
_END = {"reward", "road-back", "resurrection", "return-with-elixir"}


class HerosJourneyAdapter:
    """Hero's Journey (12-stage monomyth) structure."""

    def __init__(self) -> None:
        self._stages: list[StageDef] = [
            StageDef(
                id="ordinary-world",
                name="Ordinary World",
                description="The hero's everyday life before the adventure begins.",
                position=1,
                expected_beat_count=1,
            ),
            StageDef(
                id="call-to-adventure",
                name="Call to Adventure",
                description="A challenge or quest is presented to the hero.",
                position=2,
                expected_beat_count=1,
            ),
            StageDef(
                id="refusal",
                name="Refusal of the Call",
                description="The hero hesitates or refuses the call out of fear.",
                position=3,
                expected_beat_count=1,
            ),
            StageDef(
                id="mentor",
                name="Meeting the Mentor",
                description="The hero receives guidance, tools, or wisdom.",
                position=4,
                expected_beat_count=1,
            ),
            StageDef(
                id="crossing-threshold",
                name="Crossing the Threshold",
                description="The hero leaves the familiar world behind.",
                position=5,
                expected_beat_count=1,
            ),
            StageDef(
                id="tests-allies-enemies",
                name="Tests, Allies, Enemies",
                description="New rules, friendships, and adversaries are encountered.",
                position=6,
                expected_beat_count=2,
            ),
            StageDef(
                id="approach",
                name="Approach to the Inmost Cave",
                description="Preparation for the major ordeal ahead.",
                position=7,
                expected_beat_count=1,
            ),
            StageDef(
                id="ordeal",
                name="The Ordeal",
                description="The hero faces the greatest challenge yet.",
                position=8,
                expected_beat_count=1,
            ),
            StageDef(
                id="reward",
                name="Reward",
                description="The hero claims a treasure, knowledge, or reconciliation.",
                position=9,
                expected_beat_count=1,
            ),
            StageDef(
                id="road-back",
                name="The Road Back",
                description="The hero begins the return journey, often chased.",
                position=10,
                expected_beat_count=1,
            ),
            StageDef(
                id="resurrection",
                name="Resurrection",
                description="A final test where the hero is transformed.",
                position=11,
                expected_beat_count=1,
            ),
            StageDef(
                id="return-with-elixir",
                name="Return with the Elixir",
                description="The hero returns home changed, bearing gifts or wisdom.",
                position=12,
                expected_beat_count=1,
            ),
        ]

        self._stage_ids: set[str] = {s.id for s in self._stages}

        self._beats: dict[str, list[BeatDef]] = {
            "ordinary-world": [
                BeatDef("Status Quo", "Show the hero's normal world and its limitations.", True),
            ],
            "call-to-adventure": [
                BeatDef("The Call", "An event or message disrupts the ordinary.", True),
            ],
            "refusal": [
                BeatDef("Hesitation", "The hero doubts or resists the call.", True),
            ],
            "mentor": [
                BeatDef("Mentor Appears", "A guide offers help or a gift.", True),
            ],
            "crossing-threshold": [
                BeatDef("Threshold Crossing", "The hero steps into the special world.", True),
            ],
            "tests-allies-enemies": [
                BeatDef("Allies Gained", "The hero makes friends and learns the rules.", False),
                BeatDef("Enemies Revealed", "Opponents and obstacles emerge.", False),
            ],
            "approach": [
                BeatDef("Preparation", "Final readiness before the big test.", True),
            ],
            "ordeal": [
                BeatDef("The Ordeal", "Confrontation with the greatest fear or enemy.", True),
            ],
            "reward": [
                BeatDef("Claiming the Prize", "The hero gains something valuable.", True),
            ],
            "road-back": [
                BeatDef("Homeward Bound", "The journey back begins; stakes persist.", True),
            ],
            "resurrection": [
                BeatDef("Final Test", "Death-and-rebirth moment of transformation.", True),
            ],
            "return-with-elixir": [
                BeatDef("The Elixir", "Return home with wisdom, peace, or treasure.", True),
            ],
        }

    @property
    def structure_type(self) -> str:
        return "heros_journey"

    @property
    def stages(self) -> list[StageDef]:
        return list(self._stages)

    def suggest_stage(self, chapter_number: int, total_chapters: int) -> str:
        if total_chapters <= 0:
            return "ordinary-world"
        count = len(self._stages)
        # If chapters >= stages, map directly by ratio
        if total_chapters >= count:
            idx = min(int(((chapter_number - 1) / total_chapters) * count), count - 1)
            return self._stages[idx].id
        # Few chapters: collapse into beginning / middle / end
        ratio = chapter_number / total_chapters
        if ratio <= 1 / 3:
            return "crossing-threshold"  # last of beginning group
        if ratio <= 2 / 3:
            return "ordeal"  # central of middle group
        return "return-with-elixir"  # last of end group

    def validate_assignment(self, stage_id: str, chapter_number: int) -> bool:
        return stage_id in self._stage_ids

    def get_beat_expectations(self, stage_id: str) -> list[BeatDef]:
        return list(self._beats.get(stage_id, []))


def register(registry: StructureAdapterRegistry) -> None:
    """Module-level hook called by adapters/__init__.py during import."""
    registry.register(HerosJourneyAdapter())
