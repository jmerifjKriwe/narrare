"""Unit tests for narrare_core.notes.contracts (NOTES-001)."""

from __future__ import annotations

from uuid import uuid4

from narrare_core.notes.contracts import (
    NoteLookupProtocol,
    NoteSnapshot,
    format_note_context_block,
)


def _make_note(
    *,
    title: str | None = "Twist idea",
    content: str = "The aunt is the culprit.",
    note_type: str = "idea",
    tags: list[str] | None = None,
) -> NoteSnapshot:
    """Build a ``NoteSnapshot`` with test defaults.

    RULE-23: keyword-typed parameters instead of ``**overrides`` with a
    type-ignore cast. ``title=None`` maps to the empty stored title — the
    snapshot contract's "no title" representation; ``effective_title`` treats
    both as absent.
    """
    return NoteSnapshot(
        id=uuid4(),
        title=title if title is not None else "",
        content=content,
        note_type=note_type,
        tags=["plot"] if tags is None else tags,
    )


class TestNoteSnapshot:
    def test_display_title_uses_title_when_present(self) -> None:
        assert _make_note().display_title == "Twist idea"

    def test_display_title_falls_back_to_content(self) -> None:
        note = _make_note(title=None, content="First line of the note")
        assert note.display_title == "First line of the note"


class TestNoteLookupProtocol:
    def test_runtime_protocol_accepts_matching_shape(self) -> None:
        class _Stub:
            async def get_note_snapshot(self, note_id: object, user_id: object) -> None:
                return None

        assert isinstance(_Stub(), NoteLookupProtocol)


class TestFormatNoteContextBlock:
    def test_includes_type_tag_title_and_content(self) -> None:
        block = format_note_context_block(_make_note())
        assert block.startswith("[Note — idea [plot]]")
        assert "Twist idea" in block
        assert "The aunt is the culprit." in block

    def test_joins_multiple_tags_with_comma_space(self) -> None:
        """2+ tags render comma-space-joined inside one bracket pair."""
        block = format_note_context_block(_make_note(tags=["plot", "twist"]))
        assert block.startswith("[Note — idea [plot, twist]]")

    def test_omits_empty_tag_bracket(self) -> None:
        assert format_note_context_block(_make_note(tags=[])).startswith("[Note — idea]")

    def test_uses_display_title_fallback(self) -> None:
        note = _make_note(title=None, content="Derived title line\nbody")
        assert "Derived title line" in format_note_context_block(note)
