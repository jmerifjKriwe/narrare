"""Scene-plan persistence. All scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from typing import Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import select

from app.capabilities.planning.models import ScenePlan
from app.kernel.contracts.models import Chapter
from app.kernel.db.base import ScopedRepository


class ScenePlanRepository(ScopedRepository[ScenePlan]):
    model = ScenePlan

    async def list_for_chapter(self, chapter_id: UUID) -> Sequence[ScenePlan]:
        """The chapter's scenes in position order, scoped to the user."""
        result = await self.session.scalars(
            self.query().where(ScenePlan.chapter_id == chapter_id).order_by(ScenePlan.position)
        )
        return result.all()

    async def existing_ids(self, scene_ids: set[UUID]) -> set[UUID]:
        """The ids the user already owns, in any chapter.

        The validator's elsewhere check: an id owned elsewhere in this
        user's plans is unknown to the chapter, not a creation.
        """
        if not scene_ids:
            return set()
        result = await self.session.scalars(self.query().where(ScenePlan.id.in_(scene_ids)))
        return {scene.id for scene in result.all()}

    async def require_chapter(self, novel_id: UUID, chapter_id: UUID) -> Chapter | None:
        """The chapter when it is ours and the novel's.

        None when absent, foreign, or filed under another novel — the
        caller's 404 either way, so a foreign novel reads as missing.
        """
        return await self.session.scalar(
            select(Chapter).where(
                Chapter.id == chapter_id,
                Chapter.novel_id == novel_id,
                Chapter.user_id == self.user_id,
            )
        )

    async def create(
        self,
        chapter_id: UUID,
        changes: dict[str, Any],
    ) -> ScenePlan:
        """Flush a new scene for this user with the client's id, leaving the
        commit to the caller. The id and position arrive from the payload:
        new scenes are client-addressed, and the service has already ruled
        out the ids this user owns elsewhere."""
        scene = ScenePlan(
            user_id=self.user_id,
            chapter_id=chapter_id,
            **changes,
        )
        self.session.add(scene)
        await self.session.flush()
        return scene

    async def save(self, scene: ScenePlan, changes: dict[str, Any]) -> ScenePlan:
        """Apply an aggregate edit and flush; the commit is the caller's."""
        for field, value in changes.items():
            setattr(scene, field, value)
        await self.session.flush()
        return scene

    async def delete(self, scene: ScenePlan) -> None:
        """Mark the supplied scene for deletion; the caller commits the change."""
        await self.session.delete(scene)
