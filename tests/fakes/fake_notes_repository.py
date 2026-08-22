"""Fake NoteRepository for service-level unit tests (ADR-030 fake pattern).

Implements ``NoteRepositoryProtocol`` with in-memory storage; records calls so
tests can assert create/update/delete bookkeeping.
"""

from __future__ import annotations

import uuid

from narrare.notes.models import Note


class FakeNotesRepository:
    """In-memory NoteRepository double (ADR-030: fakes over MagicMock)."""

    def __init__(self, notes: list[Note] | None = None) -> None:
        self._notes: dict[uuid.UUID, Note] = {n.id: n for n in (notes or [])}
        self.created: list[Note] = []
        self.deleted: list[Note] = []
        self.update_calls: list[tuple[uuid.UUID, dict[str, object]]] = []

    def seed(self, note: Note) -> None:
        """Pre-populate the fake with a Note."""
        self._notes[note.id] = note

    async def get_by_id(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        note = self._notes.get(note_id)
        if note is not None and note.user_id == user_id:
            return note
        return None

    async def get_many_by_ids(self, note_ids: set[uuid.UUID], user_id: uuid.UUID) -> list[Note]:
        return [n for i, n in self._notes.items() if i in note_ids and n.user_id == user_id]

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
        result = [
            n
            for n in self._notes.values()
            if n.user_id == user_id
            and (note_type is None or n.note_type == note_type)
            and (tag is None or tag in (n.tags or []))
            and (novel_id is None or n.novel_id == novel_id)
            and (series_id is None or n.series_id == series_id)
            and (
                q is None or q.lower() in (n.title or "").lower() or q.lower() in n.content.lower()
            )
        ]
        return result[offset : offset + limit]

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
        # id is assigned here (not by the column default) to mirror the real
        # repository's post-flush state, where the Python-side uuid default
        # has been applied — callers must never see a None id.
        note = Note(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            content=content,
            note_type=note_type,
            tags=tags,
            novel_id=novel_id,
            series_id=series_id,
        )
        self._notes[note.id] = note
        self.created.append(note)
        return note

    async def update(self, note: Note, **patch: object) -> Note:
        for field, value in patch.items():
            setattr(note, field, value)
        self.update_calls.append((note.id, patch))
        return note

    async def delete(self, note: Note) -> None:
        self._notes.pop(note.id, None)
        self.deleted.append(note)

    async def distinct_tags(self, user_id: uuid.UUID, *, q: str | None = None) -> list[str]:
        tags: set[str] = set()
        for n in self._notes.values():
            if n.user_id == user_id:
                tags.update(n.tags or [])
        return sorted(t for t in tags if q is None or t.startswith(q.lower()))
