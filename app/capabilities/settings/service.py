"""Reading and writing the user's settings.

The row is the record. A browser store would keep the choice on one device and
lose it on the next, so the language lives on the user and the browser only
speaks when nobody chose. The profile's answers (W4) ride the same row: the
author name and the atelier's daily goal are the user's, not a device's.
"""

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.auth import SetupRequiredError
from app.kernel.contracts.models import User

if TYPE_CHECKING:
    from app.capabilities.settings.schemas import SettingsUpdate


class SettingsService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def read(self) -> User | None:
        # No row yet: an uninstalled instance has no preferences, and a read
        # must not create one (D14).
        return await self.session.get(User, self.user_id)

    async def write(self, update: SettingsUpdate) -> User:
        """The preference fields as one write, in one transaction.

        The locale is always carried — the schema requires it, present and
        nullable. The profile fields are partial, the novel update's rule:
        ``model_fields_set`` tells a carried ``null`` (the cleared state)
        from an absent field (no change — the language switchers carry the
        locale alone). What the body carries lands together or not at all.
        The theme keeps its own door (``write_theme``), and the write touches
        only the row of the user this service was built for.
        """
        user = await self.session.get(User, self.user_id)
        if user is None:
            raise SetupRequiredError
        user.locale = update.locale
        if "author_name" in update.model_fields_set:
            user.author_name = update.author_name
        if "daily_goal_words" in update.model_fields_set:
            user.daily_goal_words = update.daily_goal_words
        await self.session.commit()
        return user

    async def write_theme(self, theme: str | None) -> str | None:
        user = await self.session.get(User, self.user_id)
        if user is None:
            raise SetupRequiredError
        user.theme = theme
        await self.session.commit()
        return user.theme
