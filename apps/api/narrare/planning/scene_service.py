"""Scene plan aggregate service — guarded read + diff-sync save (PLAN-001).

Owns the chapter-scoped scene-plan aggregate per spec §5.3: the save path
diff-syncs by stable scene id (duplicate payload id → ValidationError;
an id absent from the chapter's rows is an insert whose PK collision on a
foreign scene id → ValidationError("unknown scene id"); ids absent from
the payload are deleted; positions are renumbered 1..N by payload order
inside the repository's single ``bulk_replace`` flush).

Ownership: uid-scoped novel guard first (foreign ≡ unknown → NotFoundError),
then the chapter-must-belong-to-novel guard. No auto-create — an empty
aggregate is a valid state (spec §5.2).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

import structlog
from sqlalchemy.exc import IntegrityError

from narrare.planning.models import ScenePlan
from narrare.planning.schemas_scenes import (
    ScenePlanAggregateResponse,
    ScenePlanSaveRequest,
    ScenePresenceSchema,
    SceneRefSchema,
    SceneSchema,
)
from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.models import Chapter
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.planning.contracts import ScenePlanRepositoryProtocol

logger = structlog.get_logger(__name__)

_SceneStatus = Literal["planned", "in_progress", "complete"]


class ScenePlanService:
    """Aggregate read + diff-sync save for a chapter's scene plans."""

    def __init__(
        self,
        scene_repo: ScenePlanRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
    ) -> None:
        self._scene_repo = scene_repo
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo

    async def get_aggregate(
        self, chapter_id: uuid.UUID, user_id: uuid.UUID, *, novel_id: uuid.UUID
    ) -> ScenePlanAggregateResponse:
        """Return the chapter's scene plans ordered by position (no auto-create)."""
        await self._guard_chapter(chapter_id, novel_id=novel_id, user_id=user_id)
        rows = await self._scene_repo.list_by_chapter(chapter_id)
        return _to_aggregate(chapter_id, rows)

    async def save_aggregate(
        self,
        chapter_id: uuid.UUID,
        request: ScenePlanSaveRequest,
        user_id: uuid.UUID,
        *,
        novel_id: uuid.UUID,
    ) -> ScenePlanAggregateResponse:
        """Whole-aggregate diff-sync per spec §5.3; returns the fresh aggregate."""
        await self._guard_chapter(chapter_id, novel_id=novel_id, user_id=user_id)

        payload_ids = [scene.id for scene in request.scenes]
        if len(set(payload_ids)) != len(payload_ids):
            raise ValidationError("duplicate scene id")

        rows = [_from_schema(scene, chapter_id) for scene in request.scenes]
        try:
            await self._scene_repo.bulk_replace(chapter_id, rows)
        except IntegrityError as exc:
            # A payload id belonging to another chapter takes the insert path
            # and collides on the PK at flush — payload integrity, not 404.
            logger.info("scene_save_unknown_scene_id", chapter_id=str(chapter_id))
            raise ValidationError("unknown scene id") from exc

        return await self.get_aggregate(chapter_id, user_id, novel_id=novel_id)

    async def _guard_chapter(
        self, chapter_id: uuid.UUID, *, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> Chapter:
        """Uid-scoped novel guard, then chapter-must-belong-to-novel guard."""
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
        chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))
        return chapter


# ---------------------------------------------------------------------------
# Module-private mapping helpers (RULE-06) — ORM row ↔ wire schema
# ---------------------------------------------------------------------------


def _to_ref_schema(raw: dict[str, object] | None) -> SceneRefSchema | None:
    """Hybrid ref dict → schema; ``None``/name-less storage maps to None."""
    if raw is None or not raw.get("name"):
        return None
    raw_id = raw.get("id")
    return SceneRefSchema(
        id=uuid.UUID(str(raw_id)) if raw_id else None,
        name=str(raw["name"]),
    )


def _to_schema(row: ScenePlan) -> SceneSchema:
    """ORM row → wire schema (hybrid refs + presences unpacked)."""
    return SceneSchema(
        id=row.id,
        position=row.position,
        title=row.title,
        pov_character_ref=_to_ref_schema(row.pov_character_ref),
        location_ref=_to_ref_schema(row.location_ref),
        present_characters=[
            ScenePresenceSchema(
                id=uuid.UUID(str(presence["id"])) if presence.get("id") else None,
                name=str(presence.get("name", "")),
                goal=str(presence.get("goal", "")),
            )
            for presence in row.present_characters or []
        ],
        purpose=row.purpose,
        conflict=row.conflict,
        resolution=row.resolution,
        beats=list(row.beats),
        status=cast("_SceneStatus", row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _from_schema(schema: SceneSchema, chapter_id: uuid.UUID) -> ScenePlan:
    """Wire schema → transient ORM row for ``bulk_replace`` (id is the diff
    key; position renumbered and timestamps DB-owned by the repository)."""
    return ScenePlan(
        id=schema.id,
        chapter_id=chapter_id,
        position=schema.position,
        title=schema.title,
        pov_character_ref=_ref_to_raw(schema.pov_character_ref),
        location_ref=_ref_to_raw(schema.location_ref),
        present_characters=[
            {
                "id": str(presence.id) if presence.id is not None else None,
                "name": presence.name,
                "goal": presence.goal,
            }
            for presence in schema.present_characters
        ],
        purpose=schema.purpose,
        conflict=schema.conflict,
        resolution=schema.resolution,
        beats=list(schema.beats),
        status=schema.status,
    )


def _ref_to_raw(ref: SceneRefSchema | None) -> dict[str, object] | None:
    """Schema ref → hybrid ref dict (user content, never rewritten — RULE-22)."""
    if ref is None:
        return None
    return {"id": str(ref.id) if ref.id is not None else None, "name": ref.name}


def _to_aggregate(chapter_id: uuid.UUID, rows: list[ScenePlan]) -> ScenePlanAggregateResponse:
    """Ordered rows → aggregate; version stamp = max(updated_at) or now()."""
    scenes = [_to_schema(row) for row in rows]
    version_updated_at = max(scene.updated_at for scene in scenes) if scenes else datetime.now(UTC)
    return ScenePlanAggregateResponse(
        chapter_id=chapter_id,
        scenes=scenes,
        version_updated_at=version_updated_at,
    )
