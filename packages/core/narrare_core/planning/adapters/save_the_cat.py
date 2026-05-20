"""Save the Cat! Structure adapter.

Blake Snyder's 15-beat structure organized into 3 acts:
  Act I  — Opening Image, Theme Stated, Set-up, Catalyst, Debate     (beats 1-5)
  Act II — Break into Two, B Story, Fun and Games, Midpoint,
           Bad Guys Close In, All Is Lost, Dark Night of Soul         (beats 6-10)
  Act III — Break into Three, Finale, Final Image                    (beats 13-15)

Each act is a "stage" and its 5 beats are the beat expectations.

Auto-registers with the module-level registry on import.
"""

from __future__ import annotations

from narrare_core.planning.adapters.base import (
    BeatDef,
    StageDef,
    StructureAdapterRegistry,
)


class SaveTheCatAdapter:
    """Save the Cat! 15-beat three-act structure."""

    def __init__(self) -> None:
        self._stages: list[StageDef] = [
            StageDef(
                id="act-1",
                name="Act I: Thesis",
                description="Establish the world, the flaw, and the catalytic event.",
                position=1,
                expected_beat_count=5,
            ),
            StageDef(
                id="act-2",
                name="Act II: Antithesis",
                description="The journey into the upside-down world; fun, games, and crisis.",
                position=2,
                expected_beat_count=5,
            ),
            StageDef(
                id="act-3",
                name="Act III: Synthesis",
                description="The hero combines lessons learned and resolves the story.",
                position=3,
                expected_beat_count=5,
            ),
        ]

        self._beats: dict[str, list[BeatDef]] = {
            "act-1": [
                BeatDef(
                    title="Opening Image",
                    description="A visual snapshot of the protagonist's starting world.",
                    required=True,
                ),
                BeatDef(
                    title="Theme Stated",
                    description="Someone hints at the story's thematic question.",
                    required=True,
                ),
                BeatDef(
                    title="Set-up",
                    description="Establish the hero's life, flaw, and what needs fixing.",
                    required=True,
                ),
                BeatDef(
                    title="Catalyst",
                    description="The event that forces the hero into action.",
                    required=True,
                ),
                BeatDef(
                    title="Debate",
                    description="The hero hesitates — should they really go?",
                    required=False,
                ),
            ],
            "act-2": [
                BeatDef(
                    title="Break into Two",
                    description="The hero decides to go and enters the new world.",
                    required=True,
                ),
                BeatDef(
                    title="B Story",
                    description="A subplot (often a relationship) carrying the theme.",
                    required=False,
                ),
                BeatDef(
                    title="Fun and Games",
                    description="The promise of the premise — exploring the new world.",
                    required=True,
                ),
                BeatDef(
                    title="Midpoint",
                    description="False victory or false defeat; stakes are raised.",
                    required=True,
                ),
                BeatDef(
                    title="Bad Guys Close In",
                    description="External pressures and internal flaws converge.",
                    required=False,
                ),
            ],
            # beats 11-12 (All Is Lost, Dark Night) are merged into act-2 end
            "act-3": [
                BeatDef(
                    title="All Is Lost",
                    description="The lowest point — something or someone is lost.",
                    required=True,
                ),
                BeatDef(
                    title="Dark Night of the Soul",
                    description="Despair before the epiphany.",
                    required=False,
                ),
                BeatDef(
                    title="Break into Three",
                    description="Inspiration strikes; the hero knows what to do.",
                    required=True,
                ),
                BeatDef(
                    title="Finale",
                    description="The hero uses lessons learned to resolve the conflict.",
                    required=True,
                ),
                BeatDef(
                    title="Final Image",
                    description="A mirror of the opening image, transformed.",
                    required=True,
                ),
            ],
        }

    @property
    def structure_type(self) -> str:
        return "save_the_cat"

    @property
    def stages(self) -> list[StageDef]:
        return list(self._stages)

    def suggest_stage(self, chapter_number: int, total_chapters: int) -> str:
        if total_chapters <= 0:
            return "act-1"
        ratio = chapter_number / total_chapters
        if ratio <= 0.25:
            return "act-1"
        if ratio <= 0.75:
            return "act-2"
        return "act-3"

    def validate_assignment(self, stage_id: str, chapter_number: int) -> bool:
        return stage_id in {"act-1", "act-2", "act-3"}

    def get_beat_expectations(self, stage_id: str) -> list[BeatDef]:
        return list(self._beats.get(stage_id, []))


def register(registry: StructureAdapterRegistry) -> None:
    """Module-level hook called by adapters/__init__.py during import."""
    registry.register(SaveTheCatAdapter())
