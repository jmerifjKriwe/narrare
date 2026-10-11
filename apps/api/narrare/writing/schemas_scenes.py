"""Writing scene-snapshot request schemas (PLAN-001 spec §8.1).

Split from ``schemas.py`` per RULE-04 (the file sat at its 200-line
config_schema limit): the structured scene input for scene-by-scene
generation. Identity-free plan data — the writer needs names and beats,
not KB linkage or ids; mirrors Core ``SceneSpec``.
"""

from __future__ import annotations

from pydantic import BaseModel


class GenerateSceneSchema(BaseModel):
    """One structured scene in a generation request (PLAN-001 spec §8.1).

    ``status`` is an unvalidated transport string by design (T9
    carry-forward — Core ``SceneSpec.status`` is a plain ``str``).
    """

    title: str = ""
    pov_character_name: str = ""
    location_name: str = ""
    present_characters: list[dict[str, str]] = []
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: list[str] = []
    status: str = "planned"
