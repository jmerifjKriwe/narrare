"""Writing logic. Routers delegate here; this module knows the unit of work."""

from collections.abc import Sequence  # noqa: TC003
from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.writing.prompts import continuation_prompt
from app.capabilities.writing.repository import ChapterRepository, EntityRepository, NovelRepository
from app.capabilities.writing.schemas import ChapterUpdate  # noqa: TC001
from app.kernel.auth import SetupRequiredError
from app.kernel.context import allocate
from app.kernel.contracts.models import Chapter, Entity, Novel, User


class NotFoundError(Exception):
    """The row does not exist or belongs to another user; the two are one answer."""


class WritingService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.novels = NovelRepository(session, user_id)
        self.chapters = ChapterRepository(session, user_id)
        self.entities = EntityRepository(session, user_id)

    async def _require_user(self) -> None:
        """Writes belong to a user that setup created; without one there is
        nothing to own the row, and the foreign key would say so at the worst
        possible time. The guard says it in the response instead."""
        if await self.session.get(User, self.user_id) is None:
            raise SetupRequiredError

    async def create_novel(
        self, title: str, genre: str | None = None, blurb: str | None = None
    ) -> Novel:
        """Commit a novel with optional genre and blurb; return the created row.

        Raise SetupRequiredError if setup has not created the owning user.
        """
        await self._require_user()
        novel = await self.novels.create(title, genre=genre, blurb=blurb)
        await self.session.commit()
        return novel

    async def list_novels(self) -> Sequence[Novel]:
        return await self.novels.list()

    async def get_novel(self, novel_id: UUID) -> Novel:
        novel = await self.novels.get(novel_id)
        if novel is None:
            raise NotFoundError
        return novel

    async def create_chapter(self, novel_id: UUID, title: str) -> Chapter:
        await self._require_user()
        if await self.novels.get(novel_id) is None:
            raise NotFoundError
        chapter = await self.chapters.create(novel_id, title)
        await self.session.commit()
        return chapter

    async def list_chapters(self, novel_id: UUID) -> Sequence[Chapter]:
        if await self.novels.get(novel_id) is None:
            raise NotFoundError
        return await self.chapters.list_for_novel(novel_id)

    async def get_chapter(self, chapter_id: UUID) -> Chapter:
        chapter = await self.chapters.get(chapter_id)
        if chapter is None:
            raise NotFoundError
        return chapter

    async def continuation_prompt(
        self,
        chapter_id: UUID,
        *,
        context_window: int | None = None,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """The prompt for a continuation, or NotFoundError if the chapter is not ours.

        `allocate` runs before any gathering, so an impossible pair refuses
        before the database is touched. The three facts default to unset —
        the allocator's own not-yet-resolved fallbacks (D7); the router passes
        the resolved profile's values. Read-only: the streamed answer comes
        back to the editor, whose autosave writes it. The request that streams
        has no side effect of its own (D14).
        """
        budgets = allocate(
            context_window=context_window, max_output_tokens=max_output_tokens, model=model
        )
        chapter = await self.get_chapter(chapter_id)
        novel = await self.novels.get(chapter.novel_id)
        tail = chapter.body[-budgets.immediate_text :] if budgets.immediate_text > 0 else ""
        folded = tail.casefold()
        ranked: list[tuple[int, Entity]] = []
        for entity in await self.entities.list_for_novel(chapter.novel_id):
            positions = [
                index
                for index in (
                    folded.find(candidate.casefold())
                    for candidate in (entity.name, *entity.aliases)
                )
                if index >= 0
            ]
            if positions:
                ranked.append((min(positions), entity))
        ranked.sort(key=lambda pair: pair[0])
        chapters = await self.chapters.list_for_novel(chapter.novel_id)
        predecessors = [
            earlier for earlier in reversed(chapters) if earlier.position < chapter.position
        ]
        return continuation_prompt(
            budgets=budgets,
            novel_title=novel.title if novel else "",
            chapter_title=chapter.title,
            body=chapter.body,
            entities=[entity for _, entity in ranked],
            predecessors=predecessors,
            genre=novel.genre if novel else None,
            blurb=novel.blurb if novel else None,
        )

    async def update_chapter(self, chapter_id: UUID, changes: ChapterUpdate) -> Chapter:
        """Commit non-null edits and update the parent novel's timestamp.

        Return the chapter; raise NotFoundError if it is absent or another user's.
        """
        chapter = await self.get_chapter(chapter_id)
        chapter = await self.chapters.save(chapter, changes.model_dump(exclude_none=True))
        await self.session.commit()
        return chapter
