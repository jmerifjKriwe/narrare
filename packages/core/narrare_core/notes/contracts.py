"""Notes contracts — pure data + protocols (RULE-03, NOTES-001).

``NoteSnapshot`` is the value object other modules (chat) consume; the API
module's NoteService implements :class:`NoteLookupProtocol`. This keeps
cross-module access on contracts, never on repositories (spec §6b).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from narrare_core.notes.types import effective_title

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(slots=True)
class NoteSnapshot:
    """Pure note snapshot for cross-module consumption (e.g. chat context)."""

    id: UUID
    title: str
    content: str
    note_type: str
    tags: list[str] = field(default_factory=list[str])

    @property
    def display_title(self) -> str:
        """Stored title, or the content-derived fallback."""
        return effective_title(self.title, self.content)


@runtime_checkable
class NoteLookupProtocol(Protocol):
    """Async note lookup by id + owner — implemented by the API notes service."""

    async def get_note_snapshot(self, note_id: UUID, user_id: UUID) -> NoteSnapshot | None: ...


def format_note_context_block(note: NoteSnapshot) -> str:
    """Serialize a note as a runtime context block for chat injection.

    RULE-02 note: this is data serialization of RUNTIME INPUT — the same
    category as ``format_history`` in ``narrare_core.chat.chat_service_core``.
    The block travels in the user-message channel; it is never a system or
    task template and contains no instructions.
    """
    tags = f" [{', '.join(note.tags)}]" if note.tags else ""
    header = f"[Note — {note.note_type}{tags}]"
    return "\n".join([header, note.display_title, "", note.content])
