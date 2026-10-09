"""Shared scene-plan test helpers (PLAN-001 T3).

Used by both scene-repository test modules — the real-repo wiring tests
(``test_repository_scenes.py``) and the fake-fidelity tests
(``test_fake_scene_plan_repository.py``). ``tests/factories.py`` gains the
official scene factory in T14; until then this helper fills the gap.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm.attributes import set_attribute

from narrare.planning.models import ScenePlan


def _scene(chapter_id: uuid.UUID | None = None, position: int = 1, **overrides: Any) -> ScenePlan:
    """ScenePlan with sensible defaults (factories gain scene helpers in T14)."""
    now = datetime.now(UTC)
    scene = ScenePlan()
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "chapter_id": chapter_id if chapter_id is not None else uuid.uuid4(),
        "position": position,
        "title": "Scene",
        "pov_character_ref": None,
        "location_ref": None,
        "present_characters": [],
        "purpose": "",
        "conflict": "",
        "resolution": "",
        "beats": [],
        "status": "planned",
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    for key, value in fields.items():
        set_attribute(scene, key, value)
    return scene
