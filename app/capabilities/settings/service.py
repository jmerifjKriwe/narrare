"""Reading and writing the user's settings.

The row is the record. A browser store would keep the choice on one device and
lose it on the next, so the language lives on the user and the browser only
speaks when nobody chose.
"""

from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.models import User


class SettingsService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def read_locale(self) -> str | None:
        user = await self.session.get(User, self.user_id)
        # No row yet: an uninstalled instance has no preference, and a read
        # must not create one (D14).
        return None if user is None else user.locale

    async def write_locale(self, locale: str | None) -> str | None:
        user = await self.session.get(User, self.user_id)
        if user is None:
            raise SetupRequiredError
        user.locale = locale
        await self.session.commit()
        return user.locale
