# apps/api/narrare/notes/repository.py
"""Note repository — DB queries only (RULE-06: no business logic here).

Implements ``NoteRepositoryProtocol`` (see ``narrare.notes.contracts``).
SQL semantics (ILIKE search, tag containment, DISTINCT unnest) were verified
against a real PostgreSQL — the unit tests exercise the wiring with a fake
session only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from narrare._app.base_repository import BaseRepository
from narrare.notes.models import Note

if TYPE_CHECKING:
    import uuid


def _escape_like(value: str) -> str:
    r"""Escape ILIKE wildcards (and the escape char itself) in user input.

    Applied wherever a LIKE/ILIKE pattern is composed from user-provided text
    so ``%``/``_`` match literally (paired with ``escape="\\"`` on the
    ``ilike`` call). Backslash is escaped first so injected escape chars
    cannot re-open a wildcard.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class NoteRepository(BaseRepository):
    """Persistence operations for scratchpad notes (NOTES-001)."""

    async def get_by_id(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        result = await self._session.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_notes(
        self,
        user_id: uuid.UUID,
        *,
        note_type: str | None = None,
        tag: str | None = None,
        novel_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]:
        """Filtered list, default sort ``updated_at DESC`` (spec §5)."""
        stmt = select(Note).where(Note.user_id == user_id)
        if note_type is not None:
            stmt = stmt.where(Note.note_type == note_type)
        if tag is not None:
            # tags @> ARRAY[tag] — containment in the TEXT[] column. Equivalent
            # to ``tag = ANY(tags)`` but statically typed (``.any`` resolves to
            # the EXISTS-style overload for ``Mapped[list[str]]``) and usable
            # by the GIN index ix_notes_tags; semantics verified against PG.
            stmt = stmt.where(Note.tags.contains([tag]))
        if novel_id is not None:
            stmt = stmt.where(Note.novel_id == novel_id)
        if series_id is not None:
            stmt = stmt.where(Note.series_id == series_id)
        if q:
            pattern = f"%{_escape_like(q)}%"
            stmt = stmt.where(
                or_(
                    Note.title.ilike(pattern, escape="\\"),
                    Note.content.ilike(pattern, escape="\\"),
                )
            )
        stmt = stmt.order_by(Note.updated_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def create(
        self,
        user_id: uuid.UUID,
        *,
        title: str | None,
        content: str,
        note_type: str,
        tags: list[str],
        novel_id: uuid.UUID | None,
        series_id: uuid.UUID | None,
    ) -> Note:
        note = Note(
            user_id=user_id,
            title=title,
            content=content,
            note_type=note_type,
            tags=tags,
            novel_id=novel_id,
            series_id=series_id,
        )
        self._session.add(note)
        await self._flush_and_refresh(note)
        return note

    async def update(self, note: Note, **patch: object) -> Note:
        """Apply a partial patch (explicit ``None`` values clear the field)."""
        for field, value in patch.items():
            setattr(note, field, value)
        await self._flush_and_refresh(note)
        return note

    async def delete(self, note: Note) -> None:
        await self._session.delete(note)
        await self._flush()

    async def distinct_tags(self, user_id: uuid.UUID, *, q: str | None = None) -> list[str]:
        """Distinct existing tags (spec §4/§9.3), optional ILIKE prefix.

        ``unnest`` runs in a subquery: PostgreSQL rejects set-returning
        functions in WHERE (``FeatureNotSupportedError`` — verified against a
        real DB), so the prefix filter must target the unnested column of the
        subquery instead of an inline ``unnest(tags)``.
        """
        unnested = (
            select(func.unnest(Note.tags).label("tag")).where(Note.user_id == user_id).subquery()
        )
        stmt = select(unnested.c.tag).distinct().order_by(unnested.c.tag)
        if q:
            stmt = stmt.where(unnested.c.tag.ilike(f"{_escape_like(q)}%", escape="\\"))
        result = await self._session.execute(stmt)
        return list(result.scalars())
