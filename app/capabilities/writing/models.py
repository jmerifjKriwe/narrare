"""Activity substrate: one net-word counter per novel per day.

The atelier's banner reads these rows across the user's novels; the
chapter write path feeds them with the diff of the shelf's one whitespace
rule. A capability-owned table, the planning substrate's pattern: only
writing reads and writes it, so it lives here, not in the kernel's shared
contracts.
"""

from datetime import date as date_type
from uuid import UUID

from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import UserOwned


class DailyWords(UserOwned):
    """One day's net words for one novel — the activity's honest delta.

    The composite primary key is the one-row-per-novel-per-day invariant;
    the write path upserts against it, so same-day writes accumulate in
    the database, never in a read-modify-write. ``words`` may go negative:
    a day that removed more text than it added shows the removal, not a
    floor of zero. The novel's foreign key cascades — a deleted book
    takes its activity with it, the chapters' own rule. The user key is
    the row's own (rule 4), so the atelier aggregate scopes without a
    join through the novel.
    """

    __tablename__ = "daily_words"

    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    words: Mapped[int] = mapped_column(default=0)
