"""Shared scene-plan service test helpers (PLAN-001 T4).

Builders + the seeded ``_World`` used by both scene-service test modules
(``test_scene_service.py`` read path, ``test_scene_service_save.py``
diff-sync path). Official scene factories land in ``tests/factories.py``
in T14; until then the T3 ``_scene`` row builder fills the gap.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from narrare.planning.schemas_scenes import ScenePlanSaveRequest, SceneSchema
from tests.factories import make_chapter, make_novel
from tests.unit.api.planning._scene_repo_test_helpers import _scene

if TYPE_CHECKING:
    from tests.fakes import FakeChapterRepository, FakeNovelRepository


class _World:
    """Seeded ids for one owner: novel, its chapter, and a foreign novel."""

    def __init__(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        self.user_id = uuid.uuid4()
        self.novel_id = uuid.uuid4()
        novel_repo.seed(make_novel(id=self.novel_id, user_id=self.user_id))
        self.chapter_id = uuid.uuid4()
        chapter_repo.seed(make_chapter(id=self.chapter_id, novel_id=self.novel_id, position=0))
        # Foreign novel owned by someone else — foreign ≡ unknown (404).
        self.foreign_novel_id = uuid.uuid4()
        novel_repo.seed(make_novel(id=self.foreign_novel_id, user_id=uuid.uuid4()))


def _scene_row(chapter_id: uuid.UUID, position: int, **overrides: Any) -> Any:
    """Stored ScenePlan row (mirrors the real table shape)."""
    return _scene(chapter_id=chapter_id, position=position, **overrides)


def _payload_scene(
    scene_id: uuid.UUID,
    position: int = 1,
    **overrides: Any,
) -> SceneSchema:
    """Client-side SceneSchema payload (timestamps required by §5.1)."""
    now = datetime.now(UTC)
    fields: dict[str, Any] = {
        "id": scene_id,
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
    return SceneSchema(**fields)


def _save_request(*scenes: SceneSchema) -> ScenePlanSaveRequest:
    return ScenePlanSaveRequest(scenes=list(scenes))
