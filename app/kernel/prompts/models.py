"""The ``PromptTemplate`` rows: a user's overrides for the bundled prompts.

The registry (:mod:`app.kernel.prompts.registry`) owns the bundled
templates; these rows are the per-user delta on top of them (plan WP4 T2).
One override lives per ``prompt_key`` either for a single novel or for the
user at large — two scopes, two rows, never a sentinel. The scope
constraint keeps one row per novel, and the database is the last word on
the global tier: ``novel_id`` NULL is distinct in the constraint, so a
partial unique index (the provider-profiles pattern) is what stops two
global rows for one key — two concurrent saves cannot both commit. The
repository is what the resolution step (T3) reads: the novel's row first,
the global one behind it.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import ScopedRepository, UserOwned


class PromptTemplate(UserOwned):
    """One user's override for one bundled prompt key, global or per novel.

    ``novel_id`` NULL is the global tier: the override stands for every
    novel the user has. A deleted novel cascades its rows at the database,
    and what remains is the global tier — the override chain's story (T3),
    not the table's.
    """

    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "novel_id", "prompt_key", name="uq_prompt_templates_novel_scope"
        ),
        # One global override per key, decided by the database: the
        # constraint above cannot see two NULLs as equal, so this partial
        # index is the last word — two concurrent creates cannot both
        # commit (F-11's shape at app/kernel/llm/models.py).
        Index(
            "uq_prompt_templates_one_global_per_key",
            "user_id",
            "prompt_key",
            unique=True,
            postgresql_where=text("novel_id IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("novels.id", ondelete="CASCADE"), index=True
    )
    # A registry key ("chat.ask" and friends); free text to the database —
    # validating a key is the caller's gate, not the schema's.
    prompt_key: Mapped[str] = mapped_column(String(80))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class PromptTemplateRepository(ScopedRepository[PromptTemplate]):
    """A user's prompt overrides, through the narrowed base.

    Every method takes the scope explicitly — ``novel_id=None`` is the
    global tier — and the commit always stays with the caller.
    """

    model = PromptTemplate

    async def _row(self, prompt_key: str, novel_id: UUID | None) -> PromptTemplate | None:
        """The user's row for exactly this scope: one novel, or the global tier."""
        return await self.session.scalar(
            self.query().where(
                PromptTemplate.prompt_key == prompt_key,
                PromptTemplate.novel_id.is_(None)
                if novel_id is None
                else PromptTemplate.novel_id == novel_id,
            )
        )

    async def effective(self, prompt_key: str, novel_id: UUID | None) -> PromptTemplate | None:
        """The override in force for the scope: the novel's row, else the global one."""
        if novel_id is not None:
            novel_row = await self._row(prompt_key, novel_id)
            if novel_row is not None:
                return novel_row
        return await self._row(prompt_key, None)

    async def save(self, prompt_key: str, content: str, novel_id: UUID | None) -> PromptTemplate:
        """Write the override for the scope, replacing its row in place."""
        row = await self._row(prompt_key, novel_id)
        if row is None:
            row = PromptTemplate(
                user_id=self.user_id, prompt_key=prompt_key, novel_id=novel_id, content=content
            )
            self.session.add(row)
        else:
            row.content = content
        await self.session.flush()
        return row

    async def delete(self, prompt_key: str, novel_id: UUID | None) -> bool:
        """Remove the override for the scope; True when a row went."""
        row = await self._row(prompt_key, novel_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True
