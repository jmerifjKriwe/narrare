"""Shared domain vocabulary: series, the shelf's grouping of novels."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import UserOwned


class Series(UserOwned):
    __tablename__ = "series"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # The name the shelf groups its volumes by. The same width as a
    # novel's title: a series is named like a book, not like a tag.
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
