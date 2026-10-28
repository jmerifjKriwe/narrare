"""First-run logic: one user, one novel, once.

The local build has exactly one user, fixed in the kernel's auth boundary. Setup
creates that row and the first novel in one transaction, so a crash leaves either
an untouched instance or a finished one.
"""

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.setup.repository import NovelRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Novel, User
from app.kernel.interchange.demos import demo_tree
from app.kernel.interchange.engine import import_archive


class AlreadySetUpError(Exception):
    """The instance has a local user; setup runs once."""


class SetupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_complete(self) -> bool:
        return await self.session.get(User, LOCAL_USER_ID) is not None

    async def complete(self, novel_title: str, demo: str | None = None) -> Novel:
        if await self.is_complete():
            raise AlreadySetUpError
        self.session.add(User(id=LOCAL_USER_ID))
        # Flush the user first: the novel's key reaches it, and the insert
        # order is a fact of this transaction, not of the unit of work's sort.
        await self.session.flush()
        if demo is None:
            novel = await NovelRepository(self.session, LOCAL_USER_ID).create(novel_title)
        else:
            # A demo is the archive's own novel: import creates it from the
            # bundled metadata (title, author, language) inside this same
            # transaction, so the user row and the demo rows commit together.
            # `novel_title` is the blank path's input, not the demo's.
            report = await import_archive(self.session, LOCAL_USER_ID, demo_tree(demo), None)
            novel = await self.session.get(Novel, report.novel_id)
            if novel is None:
                # Unreachable while the engine reports what it created in this
                # same session; an explicit named error, not an assert that
                # `python -O` strips into an AttributeError.
                raise RuntimeError(
                    f"demo import reported novel {report.novel_id} but it is not in this session"
                )
        await self.session.commit()
        return novel
