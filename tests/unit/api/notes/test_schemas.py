# tests/unit/api/notes/test_schemas.py
"""Unit tests for narrare.notes.schemas — pure Pydantic validation (NOTES-001)."""

from __future__ import annotations

from typing import ClassVar
from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.notes.schemas import (
    NoteCreateRequest,
    NoteResponse,
    NoteSearchRequest,
    NoteTagsResponse,
    NoteUpdateRequest,
)


class TestNoteCreateRequest:
    def test_minimal_request_defaults(self) -> None:
        req = NoteCreateRequest(content="A thought")
        assert req.note_type == "idea"
        assert req.tags == []
        assert req.title is None
        assert req.novel_id is None and req.series_id is None

    def test_scope_validator_rejects_both_links(self) -> None:
        with pytest.raises(ValidationError, match="not both"):
            NoteCreateRequest(content="x", novel_id=uuid4(), series_id=uuid4())

    def test_tag_count_limit(self) -> None:
        with pytest.raises(ValidationError):
            NoteCreateRequest(content="x", tags=["t"] * 11)

    def test_tag_length_limit(self) -> None:
        with pytest.raises(ValidationError):
            NoteCreateRequest(content="x", tags=["x" * 33])

    def test_content_cap_50000(self) -> None:
        with pytest.raises(ValidationError):
            NoteCreateRequest(content="x" * 50_001)


class TestNoteUpdateRequest:
    def test_all_fields_optional(self) -> None:
        req = NoteUpdateRequest()
        assert req.model_dump(exclude_unset=True) == {}

    def test_explicit_none_is_preserved_by_exclude_unset(self) -> None:
        req = NoteUpdateRequest(novel_id=None)
        assert req.model_dump(exclude_unset=True) == {"novel_id": None}

    def test_scope_validator_rejects_both_links(self) -> None:
        with pytest.raises(ValidationError, match="not both"):
            NoteUpdateRequest(novel_id=uuid4(), series_id=uuid4())


class TestNoteResponse:
    def test_from_attributes_over_orm_style_object(self) -> None:
        class _Row:
            id = uuid4()
            title = None
            content = "body"
            note_type = "idea"
            tags: ClassVar[list[str]] = ["plot"]
            novel_id = None
            series_id = None
            created_at = "2026-08-21T00:00:00+00:00"
            updated_at = "2026-08-21T00:00:00+00:00"

        resp = NoteResponse.model_validate(_Row())
        assert resp.note_type == "idea"
        assert resp.tags == ["plot"]


class TestNoteSearchRequest:
    def test_whitespace_only_query_rejected(self) -> None:
        # Regression (final review): " " passed min_length=1 and reached the
        # embedding provider, producing zero-vector semantic garbage.
        with pytest.raises(ValidationError, match="non-whitespace"):
            NoteSearchRequest(query="   ")

    def test_query_is_stripped(self) -> None:
        assert NoteSearchRequest(query="  magic  ").query == "magic"

    def test_single_char_query_accepted(self) -> None:
        assert NoteSearchRequest(query="x").query == "x"

    def test_tabs_and_newlines_are_whitespace_too(self) -> None:
        with pytest.raises(ValidationError, match="non-whitespace"):
            NoteSearchRequest(query=" \t\n ")


class TestNoteTagsResponse:
    def test_holds_tag_list(self) -> None:
        assert NoteTagsResponse(tags=["a", "b"]).tags == ["a", "b"]
