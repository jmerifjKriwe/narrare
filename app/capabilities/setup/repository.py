"""The first novel of a fresh instance, created through the scoped base like any other."""

from app.kernel.contracts.models import Novel
from app.kernel.db.base import ScopedRepository


class NovelRepository(ScopedRepository[Novel]):
    model = Novel

    async def create(self, title: str) -> Novel:
        novel = Novel(user_id=self.user_id, title=title)
        self.session.add(novel)
        await self.session.flush()
        return novel
