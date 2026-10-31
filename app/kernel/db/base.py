"""Declarative base and the one repository every user-owned row goes through."""

from typing import Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import ForeignKey, MetaData, Select, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
"""Addressable names for every constraint the models declare (design D9).

A migration must be able to name what it drops, so the convention lands
before the baseline revision, not after. It changes no DDL semantics — only
the names the database assigns to constraints the models leave unnamed.
"""


class Base(DeclarativeBase):
    """Declarative base for the kernel contracts and capability tables."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserOwned(Base):
    """Every row a user can see carries the owning user from its first version.

    The key reaches the users table, so a row cannot outlive its user or be
    created for one that setup never made."""

    __abstract__ = True

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )


class ScopedRepository[ModelT: UserOwned]:
    """Base for capability repositories.

    Every query starts from :meth:`query`, which is already narrowed to the
    requesting user. The base exposes the narrowed statement rather than the
    model, so wrapping a query in the user scope is the path of least
    resistance instead of something each repository must remember.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    def owned(self) -> Any:
        """The user predicate, for statements ``query`` cannot express.

        ``Any`` because SQLAlchemy's expression typing is invisible to pyright
        here (library types are off); the narrowed statement is the contract,
        not the annotation.
        """
        return self.model.user_id == self.user_id

    def query(self) -> Select[ModelT]:
        return select(self.model).where(self.owned())
