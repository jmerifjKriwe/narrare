"""Scene-plan aggregates: one read, one whole-aggregate diff-sync write."""

from datetime import UTC, datetime
from uuid import UUID  # noqa: TC003

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.planning.models import SCENE_STATUSES, ScenePlan
from app.capabilities.planning.repository import ScenePlanRepository
from app.capabilities.planning.schemas import (
    SceneAggregateRead,
    SceneAggregateUpdate,
    SceneRead,
    SceneUpsert,
)
from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.models import Chapter, User


class NotFoundError(Exception):
    """The chapter is absent, foreign, or filed under another novel."""


class SceneRefusedError(ValueError):
    """A PUT the diff-sync law refuses: a doubled id, an id owned elsewhere,
    or a status outside the lifecycle."""


class PlanningService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.scenes = ScenePlanRepository(session, user_id)

    async def _require_user(self) -> None:
        """Writes belong to a user that setup created; without one there is
        nothing to own the row, and the foreign key would say so at the worst
        possible time. The guard says it in the response instead."""
        if await self.session.get(User, self.user_id) is None:
            raise SetupRequiredError

    async def _require_chapter(self, novel_id: UUID, chapter_id: UUID) -> Chapter:
        """The chapter when it is ours and the novel's; NotFoundError for an
        absent or unowned chapter, a foreign novel, or a chapter filed under
        another novel — all three read as missing, never as an oracle."""
        chapter = await self.scenes.require_chapter(novel_id, chapter_id)
        if chapter is None:
            raise NotFoundError
        return chapter

    def _read(self, chapter: Chapter, scenes: list[ScenePlan]) -> SceneAggregateRead:
        """The aggregate shape: the chapter's scenes in position order, with
        the chapter's own stamp as the version the dock compares against."""
        return SceneAggregateRead(
            chapter_id=chapter.id,
            scenes=[SceneRead.model_validate(scene) for scene in scenes],
            version_updated_at=chapter.updated_at,
        )

    async def get_aggregate(self, novel_id: UUID, chapter_id: UUID) -> SceneAggregateRead:
        """Read the chapter's scenes in position order. No auto-create: a
        chapter without plans answers with an empty list. Raise NotFoundError
        for an absent or unowned chapter."""
        chapter = await self._require_chapter(novel_id, chapter_id)
        return self._read(chapter, list(await self.scenes.list_for_chapter(chapter.id)))

    async def save_aggregate(
        self, novel_id: UUID, chapter_id: UUID, payload: SceneAggregateUpdate
    ) -> SceneAggregateRead:
        """Diff the whole aggregate by stable scene id and commit once.

        A known id updates, an id from another chapter is a 422, a doubled
        id is a 422, an absent id deletes, and positions renumber 1..N by
        payload order. Every refusal lands before any write, so a refused
        PUT leaves the aggregate exactly as the refetch found it. Raise
        NotFoundError for an absent or unowned chapter.
        """
        await self._require_user()
        chapter = await self._require_chapter(novel_id, chapter_id)
        current = {scene.id: scene for scene in await self.scenes.list_for_chapter(chapter.id)}
        held = await self._refuse_before_write(payload.scenes, set(current))
        created = [upsert.id for upsert in payload.scenes if upsert.id not in current]
        try:
            for position, upsert in enumerate(payload.scenes, start=1):
                if upsert.id in current:
                    await self.scenes.save(current[upsert.id], self._changes(upsert, position))
                else:
                    await self.scenes.create(chapter.id, self._changes(upsert, position))
            for stale_id in set(current) - held:
                await self.scenes.delete(current[stale_id])
            # The chapter carries the version: an aggregate write counts as
            # touching the chapter, so the stamp the dock compares moves with
            # every PUT — a scenes-only write would leave it honestly stale.
            chapter.updated_at = datetime.now(UTC)
            await self.session.commit()
        except IntegrityError:
            # A client id that reached the INSERT but belongs to another
            # user's plans: the primary key says so, and the answer is the
            # same 422 the elsewhere check gives for this user's own rows —
            # naming the created ids the way that check names its id.
            await self.session.rollback()
            detail = (
                "unknown scene id"
                if not created
                else (
                    f"unknown scene id: {', '.join(sorted(str(scene_id) for scene_id in created))}"
                )
            )
            raise SceneRefusedError(detail) from None
        return self._read(chapter, list(await self.scenes.list_for_chapter(chapter.id)))

    async def _refuse_before_write(self, upserts: list[SceneUpsert], known: set[UUID]) -> set[UUID]:
        """The diff-sync law's refusals, all before any write.

        A doubled id, a status outside the lifecycle, or an id the user owns
        in another chapter — each names its reason, and a refused PUT writes
        nothing at all. Returns the payload's ids for the delete pass.
        """
        seen: set[UUID] = set()
        for upsert in upserts:
            if upsert.id in seen:
                raise SceneRefusedError(f"duplicate scene id: {upsert.id}")
            seen.add(upsert.id)
            if upsert.status not in SCENE_STATUSES:
                raise SceneRefusedError(f"unknown status: {upsert.status}")
        owned_elsewhere = await self.scenes.existing_ids(seen - known)
        for scene_id in sorted(seen & owned_elsewhere, key=str):
            raise SceneRefusedError(f"unknown scene id: {scene_id}")
        return seen

    @staticmethod
    def _changes(upsert: SceneUpsert, position: int) -> dict[str, object]:
        """The payload's writable fields: positions renumber 1..N by payload
        order, and the timestamps stay the server's — the schema carries no
        field for them, so a forged value never arrives here."""
        return {
            "id": upsert.id,
            "title": upsert.title,
            "purpose": upsert.purpose,
            "conflict": upsert.conflict,
            "resolution": upsert.resolution,
            "beats": list(upsert.beats),
            "status": upsert.status,
            "position": position,
        }
