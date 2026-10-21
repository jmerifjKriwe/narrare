"""First-run logic: one user, one novel, once.

The local build has exactly one user, fixed in the kernel's auth boundary. Setup
creates that row and the first novel in one transaction, so a crash leaves either
an untouched instance or a finished one.
"""

from app.capabilities.setup.repository import NovelRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Novel, User
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002


class AlreadySetUpError(Exception):
    """The instance has a local user; setup runs once."""


class SetupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_complete(self) -> bool:
        return await self.session.get(User, LOCAL_USER_ID) is not None

    async def complete(self, novel_title: str) -> Novel:
        if await self.is_complete():
            raise AlreadySetUpError
        self.session.add(User(id=LOCAL_USER_ID))
        novel = await NovelRepository(self.session, LOCAL_USER_ID).create(novel_title)
        await self.session.commit()
        return novel
