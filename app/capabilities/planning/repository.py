"""Scene-plan and timeline-event persistence. All scoped to one user."""

from collections.abc import Sequence  # noqa: TC003
from typing import Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import select

from app.capabilities.planning.models import ScenePlan, TimelineEvent
from app.kernel.contracts.models import Chapter, Novel
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


class TimelineEventRepository(ScopedRepository[TimelineEvent]):
    model = TimelineEvent

    async def list_for_novel(self, novel_id: UUID) -> Sequence[TimelineEvent]:
        """The novel's events in manual order, scoped to the user.

        Unordered rows (null position) sort last, creation order breaks the
        position tie, and the id breaks what is left — the canvas order the
        writer arranged, dateless rows at the end, fully deterministic.
        """
        result = await self.session.scalars(
            self.query()
            .where(TimelineEvent.novel_id == novel_id)
            .order_by(
                TimelineEvent.position.asc().nulls_last(),
                TimelineEvent.created_at.asc(),
                TimelineEvent.id.asc(),
            )
        )
        return result.all()

    async def get_for_novel(self, novel_id: UUID, event_id: UUID) -> TimelineEvent | None:
        """The event when it is ours and the novel's; None otherwise."""
        return await self.session.scalar(
            self.query().where(TimelineEvent.id == event_id, TimelineEvent.novel_id == novel_id)
        )

    async def require_novel(self, novel_id: UUID) -> Novel | None:
        """The novel when it is ours; None when absent or foreign — the
        caller's 404 either way, so a foreign novel reads as missing."""
        return await self.session.scalar(
            select(Novel).where(Novel.id == novel_id, Novel.user_id == self.user_id)
        )

    async def require_chapter(self, novel_id: UUID, chapter_id: UUID) -> Chapter | None:
        """The chapter when it is ours and the novel's; None otherwise."""
        return await self.session.scalar(
            select(Chapter).where(
                Chapter.id == chapter_id,
                Chapter.novel_id == novel_id,
                Chapter.user_id == self.user_id,
            )
        )

    async def create(
        self,
        novel_id: UUID,
        changes: dict[str, Any],
    ) -> TimelineEvent:
        """Flush a new event for this user and novel, leaving the commit to
        the caller."""
        event = TimelineEvent(
            user_id=self.user_id,
            novel_id=novel_id,
            **changes,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def save(self, event: TimelineEvent, changes: dict[str, Any]) -> TimelineEvent:
        """Apply an edit and flush; the commit is the caller's."""
        for field, value in changes.items():
            setattr(event, field, value)
        await self.session.flush()
        return event

    async def delete(self, event: TimelineEvent) -> None:
        """Mark the supplied event for deletion; the caller commits the change."""
        await self.session.delete(event)
