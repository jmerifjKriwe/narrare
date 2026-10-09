"""Output types for ScenePlanAgent.

Scene-planning structured outputs per PLAN-001 spec §6.1 (ADR-096):
a draft run proposes N scenes for a chapter, a refine run rewrites one
scene under the author's instruction. Field names mirror the scene wire
shapes (spec §5.1) so API mapping stays 1:1.
"""

from __future__ import annotations

from pydantic import BaseModel


class ScenePresenceModel(BaseModel):
    """A character present in a scene.

    Attributes:
        name: Character name (resolved against the cast at save time).
        goal: What the character wants during the scene (may be empty).
    """

    name: str
    goal: str = ""


class SceneProposal(BaseModel):
    """A single proposed scene — draft item or refine result.

    Carries no id/position/status: those are assigned when the proposal
    is accepted into the scene plan aggregate (AI endpoints never write).

    Attributes:
        title: Scene title (may be empty while purpose carries substance).
        pov_character_name: Point-of-view character name.
        location_name: Location name.
        present_characters: Characters present, each with an optional goal.
        purpose: What the scene accomplishes in the story.
        conflict: The scene-level conflict.
        resolution: How the conflict resolves.
        beats: Ordered story beats within the scene.
    """

    title: str = ""
    pov_character_name: str = ""
    location_name: str = ""
    present_characters: list[ScenePresenceModel] = []
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: list[str] = []


class SceneDraftOutput(BaseModel):
    """Structured output of a scene-plan draft run (chapter → N scenes)."""

    scenes: list[SceneProposal] = []


class SceneRefineOutput(BaseModel):
    """Structured output of a scene-plan refine run (one constrained rewrite)."""

    scene: SceneProposal


class ScenePlanDeps:
    """Dependencies for ScenePlanAgent.

    Attributes:
        language: Output language code (default "en").
        genre: Story genre (e.g. "Fantasy").
        project_title: Title of the novel being planned.
    """

    def __init__(
        self,
        language: str = "en",
        genre: str = "",
        project_title: str = "",
    ) -> None:
        self.language = language
        self.genre = genre
        self.project_title = project_title
