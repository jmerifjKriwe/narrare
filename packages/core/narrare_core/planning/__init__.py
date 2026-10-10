"""Planning domain module — storyboard structure adapters and sync logic.

Owns structure adapters (three-act, five-act, hero's journey, etc.),
sync status models, and pure domain logic for the storyboard feature.
No HTTP, no database sessions, no LLM calls.
"""

from narrare_core.planning.adapters import (
    StageDef,
    StructureAdapter,
    StructureAdapterRegistry,
    registry,
)
from narrare_core.planning.models import (
    ChapterOutlineData,
    ScenePlanData,
    ScenePresence,
    SceneStatus,
    StageAssignment,
    StoryboardView,
    SyncStatus,
)
from narrare_core.planning.scene_render import render_scene_for_prompt
from narrare_core.planning.sync import StructuralSyncChecker

__all__ = [
    "ChapterOutlineData",
    "ScenePlanData",
    "ScenePresence",
    "SceneStatus",
    "StageAssignment",
    "StageDef",
    "StoryboardView",
    "StructuralSyncChecker",
    "StructureAdapter",
    "StructureAdapterRegistry",
    "SyncStatus",
    "registry",
    "render_scene_for_prompt",
]
