"""Chapter numbering: one allocator, one lock, wherever a chapter is appended.

Reading ``max(position)`` and writing it back is two statements with a commit
between them for everyone else in the book — a second click on "Neues
Kapitel", or an import landing beside a creation, otherwise takes the same
number and the rail shows "Kapitel 1" twice with no order between the rows
(#521). The parent novel row is the lock: the second writer waits, then reads
the first writer's committed chapter.

Two paths append chapters — the writing repository and the import engine — so
this lives in the kernel vocabulary they share rather than in either of them.
"""

from uuid import UUID  # noqa: TC003

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.contracts.models import Chapter, Novel


async def next_chapter_position(session: AsyncSession, *, user_id: UUID, novel_id: UUID) -> int:
    """Lock the book, then the number one past its last chapter.

    Must be called before the caller's own insert and inside its transaction:
    the lock is held until that commit, which is what serialises the writers.
    """
    await session.execute(
        select(Novel.id).where(Novel.id == novel_id, Novel.user_id == user_id).with_for_update()
    )
    current = await session.scalar(
        select(func.max(Chapter.position)).where(
            Chapter.novel_id == novel_id, Chapter.user_id == user_id
        )
    )
    return 0 if current is None else current + 1
