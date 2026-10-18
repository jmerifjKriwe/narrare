"""Unit tests for session_mapper — session → KBEntryCreate mapping.

Tests the mapping strategy: name, entity_type, metadata unflattening,
and body construction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from narrare.kb.session_mapper import _build_body, _unflatten_fields, map_session_to_entry
from narrare.kb.session_models import KBCreationField, KBCreationSession

# ---------------------------------------------------------------------------
# Tests: _unflatten_fields (unit helper)
# ---------------------------------------------------------------------------


class TestUnflattenFields:
    """Test dot-notation field unflattening."""

    def test_flat_fields_stay_top_level(self) -> None:
        """Fields without dots remain at the top level."""
        result = _unflatten_fields({"name": "Aria", "role": "protagonist"})
        assert result == {"name": "Aria", "role": "protagonist"}

    def test_dot_notation_creates_nested_dict(self) -> None:
        """Dot notation creates nested dictionaries."""
        result = _unflatten_fields({"appearance.height": "180cm"})
        assert result == {"appearance": {"height": "180cm"}}

    def test_multiple_dots_create_deep_nesting(self) -> None:
        """Multiple dots create deep nesting."""
        result = _unflatten_fields({"a.b.c": "deep"})
        assert result == {"a": {"b": {"c": "deep"}}}

    def test_mixed_flat_and_nested(self) -> None:
        """Mixed flat and nested fields are handled."""
        result = _unflatten_fields(
            {
                "name": "Aria",
                "appearance.height": "180cm",
                "appearance.eyes": "blue",
            }
        )
        assert result == {
            "name": "Aria",
            "appearance": {"height": "180cm", "eyes": "blue"},
        }

    def test_empty_dict_returns_empty(self) -> None:
        """Empty input returns empty dict."""
        assert _unflatten_fields({}) == {}


# ---------------------------------------------------------------------------
# Tests: _build_body (unit helper)
# ---------------------------------------------------------------------------


class TestBuildBody:
    """Test structured markdown body generation."""

    def test_basic_body(self) -> None:
        """Body includes name heading and type."""
        body = _build_body("Aria", "character", {"role": "protagonist"})
        assert "# Aria" in body
        assert "**Type:** character" in body
        assert "**Role:** protagonist" in body

    def test_dot_notation_label(self) -> None:
        """Dot notation keys are rendered with > separators."""
        body = _build_body(
            "Aria",
            "character",
            {"appearance.height": "180cm"},
        )
        assert "**Appearance > Height:** 180cm" in body

    def test_underscore_to_space(self) -> None:
        """Underscores in keys become spaces in labels."""
        body = _build_body("Aria", "character", {"hair_color": "brown"})
        assert "**Hair Color:** brown" in body

    def test_empty_fields(self) -> None:
        """Empty field dict produces minimal body."""
        body = _build_body("Aria", "character", {})
        assert body == "# Aria\n\n**Type:** character"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    name: str | None = "Aria",
    entity_type: str = "character",
    fields: list[KBCreationField] | None = None,
) -> KBCreationSession:
    """Create a test session with given params."""
    if fields is None:
        fields = [
            KBCreationField(
                field_key="role",
                label="Role",
                user_value="protagonist",
                source="user",
                final_value="protagonist",
            ),
            KBCreationField(
                field_key="appearance.height",
                label="Appearance Height",
                ai_suggested_value="180cm",
                source="ai",
                final_value="180cm",
            ),
        ]
    return KBCreationSession(
        id=uuid4(),
        novel_id=uuid4(),
        user_id=uuid4(),
        entity_type=entity_type,
        name=name,
        fields=fields,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Tests: map_session_to_entry
# ---------------------------------------------------------------------------


class TestMapSessionToEntry:
    """Test session → KBEntryCreate mapping."""

    def test_happy_path_character_session(self) -> None:
        """Character session maps to KBEntryCreate with all fields."""
        entry = map_session_to_entry(_make_session())

        assert entry.entity_type == "character"
        assert entry.name == "Aria"
        assert entry.status == "draft"

        # Metadata should have unflattened fields
        assert entry.metadata is not None
        assert entry.metadata["role"] == "protagonist"
        assert isinstance(entry.metadata["appearance"], dict)
        assert entry.metadata["appearance"]["height"] == "180cm"  # type: ignore[index]

        # Body should be structured markdown
        assert entry.body is not None
        assert "# Aria" in entry.body
        assert "**Type:** character" in entry.body

    def test_raises_value_error_without_name(self) -> None:
        """Session without name raises ValueError."""
        session = _make_session(name=None)
        with pytest.raises(ValueError, match="Session must have a name"):
            map_session_to_entry(session)

    def test_mapped_entry_without_tags_defaults_to_empty_list(self) -> None:
        """Sessions have no tag concept — mapped entries carry tags=[], never None.

        Regression guard (F10, 2026-10-17): the mapper omitted tags and the
        schema default was None, so session-created entries persisted null
        and the FE list crashed on ``entry.tags.length``. The empty list is
        the honest value; the schema seam (T7 pattern) defaults omission
        centrally for every KBEntryCreate caller.
        """
        entry = map_session_to_entry(_make_session())

        assert entry.tags == []

    def test_empty_name_raises_value_error(self) -> None:
        """Session with empty string name raises."""
        session = _make_session(name="")
        with pytest.raises(ValueError, match="Session must have a name"):
            map_session_to_entry(session)

    def test_skips_empty_fields(self) -> None:
        """Fields without any value are skipped in metadata and body."""
        fields = [
            KBCreationField(field_key="role", label="Role"),
            # no values set
        ]
        session = _make_session(fields=fields)
        entry = map_session_to_entry(session)

        # Empty fields should not appear
        if entry.metadata:
            assert "role" not in entry.metadata

    def test_location_session_maps_correctly(self) -> None:
        """Location session correctly maps entity type."""
        fields = [
            KBCreationField(
                field_key="climate",
                label="Climate",
                user_value="temperate",
                source="user",
                final_value="temperate",
            ),
        ]
        session = _make_session(name="Elmwood Forest", entity_type="location", fields=fields)
        entry = map_session_to_entry(session)

        assert entry.entity_type == "location"
        assert entry.name == "Elmwood Forest"
        assert entry.metadata is not None
        assert entry.metadata["climate"] == "temperate"

    def test_final_value_precedence(self) -> None:
        """final_value takes precedence over user_value and ai_suggested_value."""
        fields = [
            KBCreationField(
                field_key="role",
                label="Role",
                user_value="protagonist",
                ai_suggested_value="antagonist",
                final_value="protagonist",
                source="user",
            ),
        ]
        session = _make_session(fields=fields)
        entry = map_session_to_entry(session)

        assert entry.metadata is not None
        assert entry.metadata["role"] == "protagonist"
