"""Novel persistence. Scoped: a repository instance can only see one user's rows."""

from collections.abc import Sequence  # noqa: TC003

from app.kernel.contracts.models import Novel
from app.kernel.db.base import ScopedRepository


class NovelRepository(ScopedRepository[Novel]):
    model = Novel

    async def list(self) -> Sequence[Novel]:
        result = await self.session.scalars(self.query().order_by(Novel.created_at.desc()))
        return result.all()

    async def create(self, title: str) -> Novel:
        novel = Novel(user_id=self.user_id, title=title)
        self.session.add(novel)
        await self.session.flush()
        return novel
