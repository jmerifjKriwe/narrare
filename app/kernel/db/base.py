"""Declarative base and the one repository every user-owned row goes through."""

from uuid import UUID  # noqa: TC003

from sqlalchemy import Select, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for the kernel contracts and capability tables."""


class UserOwned(Base):
    """Every row a user can see carries the owning user from its first migration."""

    __abstract__ = True

    user_id: Mapped[UUID] = mapped_column(Uuid, index=True)


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

    def query(self) -> Select[ModelT]:
        return select(self.model).where(self.model.user_id == self.user_id)
