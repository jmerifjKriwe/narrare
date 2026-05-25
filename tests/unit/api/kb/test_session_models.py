"""Unit tests for KB creation session models.

Tests KBCreationField and KBCreationSession creation, validation,
field updates, status transitions, and JSON serialization.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from narrare.kb.session_models import KBCreationField, KBCreationSession

# ---------------------------------------------------------------------------
# KBCreationField
# ---------------------------------------------------------------------------


class TestKBCreationFieldCreation:
    """Test KBCreationField instantiation and defaults."""

    def test_minimal_creation(self) -> None:
        """Create a field with only required attributes."""
        field = KBCreationField(field_key="name", label="Name")
        assert field.field_key == "name"
        assert field.label == "Name"
        assert field.field_type == "text"
        assert field.required is False
        assert field.options is None
        assert field.user_value is None
        assert field.ai_suggested_value is None
        assert field.ai_reasoning is None
        assert field.source == "user"
        assert field.final_value is None

    def test_full_creation(self) -> None:
        """Create a field with all attributes specified."""
        field = KBCreationField(
            field_key="role",
            label="Role",
            field_type="select",
            required=True,
            options=["protagonist", "antagonist", "supporting"],
            user_value="protagonist",
            ai_suggested_value="hero",
            ai_reasoning="Based on story structure",
            source="user",
            final_value="protagonist",
        )
        assert field.field_type == "select"
        assert field.required is True
        assert field.options == ["protagonist", "antagonist", "supporting"]
        assert field.user_value == "protagonist"

    def test_invalid_field_type_rejected(self) -> None:
        """Invalid field_type raises ValidationError."""
        with pytest.raises(ValidationError):
            KBCreationField(field_key="x", label="X", field_type="invalid")  # type: ignore[call-arg]

    def test_invalid_source_rejected(self) -> None:
        """Invalid source raises ValidationError."""
        with pytest.raises(ValidationError):
            KBCreationField(field_key="x", label="X", source="unknown")  # type: ignore[call-arg]

    def test_list_field_type(self) -> None:
        """list field_type is accepted."""
        field = KBCreationField(field_key="traits", label="Traits", field_type="list")
        assert field.field_type == "list"

    def test_boolean_field_type(self) -> None:
        """boolean field_type is accepted."""
        field = KBCreationField(field_key="pov", label="POV", field_type="boolean")
        assert field.field_type == "boolean"


class TestKBCreationFieldUpdates:
    """Test updating field values."""

    def test_user_value_update(self) -> None:
        """Setting user_value and final_value."""
        field = KBCreationField(field_key="name", label="Name")
        field.user_value = "Aria"
        field.source = "user"
        field.final_value = "Aria"
        assert field.user_value == "Aria"
        assert field.final_value == "Aria"
        assert field.source == "user"

    def test_ai_suggested_value_update(self) -> None:
        """Setting ai_suggested_value and reasoning."""
        field = KBCreationField(field_key="name", label="Name")
        field.ai_suggested_value = "Elena"
        field.ai_reasoning = "Common fantasy name"
        assert field.ai_suggested_value == "Elena"
        assert field.ai_reasoning == "Common fantasy name"


# ---------------------------------------------------------------------------
# KBCreationSession
# ---------------------------------------------------------------------------


class TestKBCreationSessionCreation:
    """Test KBCreationSession instantiation and defaults."""

    def test_minimal_creation(self) -> None:
        """Create a session with required fields only."""
        from uuid import uuid4

        session = KBCreationSession(
            id=uuid4(),
            novel_id=uuid4(),
            user_id=uuid4(),
            entity_type="character",
        )
        assert session.status == "active"
        assert session.fields == []
        assert session.context_entries == []
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)

    def test_with_fields(self) -> None:
        """Create a session with pre-populated fields."""
        from uuid import uuid4

        fields = [
            KBCreationField(field_key="name", label="Name", required=True),
            KBCreationField(field_key="age", label="Age"),
        ]
        session = KBCreationSession(
            id=uuid4(),
            novel_id=uuid4(),
            user_id=uuid4(),
            entity_type="character",
            fields=fields,
        )
        assert len(session.fields) == 2
        assert session.fields[0].field_key == "name"

    def test_invalid_status_rejected(self) -> None:
        """Invalid status raises ValidationError."""
        from uuid import uuid4

        with pytest.raises(ValidationError):
            KBCreationSession(
                id=uuid4(),
                novel_id=uuid4(),
                user_id=uuid4(),
                entity_type="character",
                status="unknown",  # type: ignore[call-arg]
            )


class TestKBCreationSessionStatusTransitions:
    """Test session status transitions."""

    def _make_session(self, status: str = "active") -> KBCreationSession:
        from uuid import uuid4

        return KBCreationSession(
            id=uuid4(),
            novel_id=uuid4(),
            user_id=uuid4(),
            entity_type="character",
            status=status,  # type: ignore[arg-type]
        )

    def test_active_to_review(self) -> None:
        """Transition from active to review."""
        session = self._make_session("active")
        session.status = "review"
        assert session.status == "review"

    def test_active_to_complete(self) -> None:
        """Transition from active to complete."""
        session = self._make_session("active")
        session.status = "complete"
        assert session.status == "complete"

    def test_active_to_abandoned(self) -> None:
        """Transition from active to abandoned."""
        session = self._make_session("active")
        session.status = "abandoned"
        assert session.status == "abandoned"

    def test_review_to_complete(self) -> None:
        """Transition from review to complete."""
        session = self._make_session("review")
        session.status = "complete"
        assert session.status == "complete"


class TestKBCreationSessionSerialization:
    """Test JSON round-trip serialization."""

    def test_json_round_trip(self) -> None:
        """Session survives JSON serialization and deserialization."""
        from uuid import uuid4

        fields = [
            KBCreationField(
                field_key="name",
                label="Name",
                required=True,
                user_value="Aria",
                source="user",
                final_value="Aria",
            ),
            KBCreationField(
                field_key="role",
                label="Role",
                ai_suggested_value="protagonist",
                ai_reasoning="Story structure analysis",
            ),
        ]
        original = KBCreationSession(
            id=uuid4(),
            novel_id=uuid4(),
            user_id=uuid4(),
            entity_type="character",
            fields=fields,
            context_entries=["entry1"],
        )

        json_str = original.model_dump_json()
        restored = KBCreationSession.model_validate_json(json_str)

        assert restored.id == original.id
        assert restored.novel_id == original.novel_id
        assert restored.entity_type == original.entity_type
        assert restored.status == original.status
        assert len(restored.fields) == 2
        assert restored.fields[0].user_value == "Aria"
        assert restored.fields[1].ai_suggested_value == "protagonist"
        assert restored.context_entries == ["entry1"]

    def test_model_dump_mode_json(self) -> None:
        """model_dump(mode='json') produces JSON-safe types."""
        from uuid import uuid4

        session = KBCreationSession(
            id=uuid4(),
            novel_id=uuid4(),
            user_id=uuid4(),
            entity_type="character",
        )
        data = session.model_dump(mode="json")
        # UUIDs should be strings in JSON mode
        assert isinstance(data["id"], str)
        assert isinstance(data["novel_id"], str)
