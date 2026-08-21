"""Scratchpad notes core module (NOTES-001) — pure types and contracts."""

from narrare_core.notes.contracts import (
    NoteLookupProtocol,
    NoteSnapshot,
    format_note_context_block,
)
from narrare_core.notes.types import (
    DEFAULT_NOTE_LIMITS,
    NoteLimits,
    NoteType,
    ScopeError,
    effective_title,
    fallback_title,
    normalize_tag,
    normalize_tags,
    validate_scope,
)

__all__ = [
    "DEFAULT_NOTE_LIMITS",
    "NoteLimits",
    "NoteLookupProtocol",
    "NoteSnapshot",
    "NoteType",
    "ScopeError",
    "effective_title",
    "fallback_title",
    "format_note_context_block",
    "normalize_tag",
    "normalize_tags",
    "validate_scope",
]
