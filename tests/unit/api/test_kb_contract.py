"""Contract test: KB Pydantic schemas match frontend expectations.

The frontend consumes KBEntryResponse, KBRelationshipResponse, etc.
Field name and type mismatches cause runtime crashes. This test ensures
the schemas expose the expected fields with expected types.
"""

from __future__ import annotations

from uuid import UUID


class TestKBEntryResponseContract:
    """KBEntryResponse must expose expected fields for frontend consumption."""

    def test_kb_entry_response_has_required_fields(self) -> None:
        from narrare.kb.schemas import KBEntryResponse

        field_names = set(KBEntryResponse.model_fields.keys())
        expected = {
            "id",
            "novel_id",
            "entity_type",
            "name",
            "slug",
            "status",
            "tags",
            "body",
            "template_version",
            "embeddings_dirty",
            "created_at",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"KBEntryResponse is missing fields: {missing}"

    def test_kb_entry_response_id_is_uuid(self) -> None:
        from narrare.kb.schemas import KBEntryResponse

        ann = KBEntryResponse.model_fields["id"].annotation
        assert ann is UUID, f"Expected id to be UUID, got {ann}"

    def test_kb_entry_response_name_is_str(self) -> None:
        from narrare.kb.schemas import KBEntryResponse

        ann = KBEntryResponse.model_fields["name"].annotation
        assert ann is str, f"Expected name to be str, got {ann}"


class TestKBEntryListResponseContract:
    """KBEntryListResponse carries pagination metadata."""

    def test_has_items_total_page_page_size(self) -> None:
        from narrare.kb.schemas import KBEntryListResponse

        field_names = set(KBEntryListResponse.model_fields.keys())
        for f in ("items", "total", "page", "page_size"):
            assert f in field_names, f"KBEntryListResponse missing field '{f}'"


class TestKBRelationshipResponseContract:
    """KBRelationshipResponse must expose expected fields."""

    def test_relationship_response_has_required_fields(self) -> None:
        from narrare.kb.schemas import KBRelationshipResponse

        field_names = set(KBRelationshipResponse.model_fields.keys())
        expected = {
            "id",
            "source_id",
            "target_id",
            "rel_type",
            "label",
            "direction",
            "source_name",
            "target_name",
            "created_at",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"KBRelationshipResponse is missing fields: {missing}"

    def test_relationship_response_source_and_target_names_optional(self) -> None:
        from narrare.kb.schemas import KBRelationshipResponse

        source_name = KBRelationshipResponse.model_fields["source_name"]
        assert source_name.default is None, "source_name should default to None"
        target_name = KBRelationshipResponse.model_fields["target_name"]
        assert target_name.default is None, "target_name should default to None"


class TestKBEntryCreateContract:
    """KBEntryCreate request schema field contract."""

    def test_create_has_required_fields(self) -> None:
        from narrare.kb.schemas import KBEntryCreate

        field_names = set(KBEntryCreate.model_fields.keys())
        for f in ("entity_type", "name"):
            assert f in field_names, f"KBEntryCreate missing field '{f}'"

    def test_create_entity_type_has_min_length(self) -> None:
        from narrare.kb.schemas import KBEntryCreate

        field = KBEntryCreate.model_fields["entity_type"]
        # Check the min_length constraint via the metadata
        constraints = _get_constraints(field)
        assert constraints.get("min_length") == 1, "entity_type min_length should be 1"

    def test_create_slug_is_optional(self) -> None:
        from narrare.kb.schemas import KBEntryCreate

        assert KBEntryCreate.model_fields["slug"].default is None, "slug should be optional"


class TestKBRelationshipCreateContract:
    """KBRelationshipCreate request schema field contract."""

    def test_create_has_source_and_target(self) -> None:
        from narrare.kb.schemas import KBRelationshipCreate

        field_names = set(KBRelationshipCreate.model_fields.keys())
        for f in ("source_id", "target_id", "rel_type"):
            assert f in field_names, f"KBRelationshipCreate missing field '{f}'"


class TestResolveReferencesResponseContract:
    """ResolveReferencesResponse schema contract."""

    def test_response_has_resolved_list(self) -> None:
        from narrare.kb.schemas import ResolveReferencesResponse

        field_names = set(ResolveReferencesResponse.model_fields.keys())
        assert "resolved" in field_names, "ResolveReferencesResponse missing 'resolved'"

    def test_reference_resolution_has_mention_and_entry_id(self) -> None:
        from narrare.kb.schemas import ReferenceResolution

        field_names = set(ReferenceResolution.model_fields.keys())
        for f in ("mention", "entry_id", "entry_name", "entity_type", "slug"):
            assert f in field_names, f"ReferenceResolution missing field '{f}'"


def _get_constraints(field: object) -> dict[str, object]:
    """Extract Pydantic constraints from a FieldInfo as a dict."""
    from pydantic.fields import FieldInfo

    if not isinstance(field, FieldInfo):  # type: ignore[arg-type]
        return {}
    constraints: dict[str, object] = {}
    # Pydantic v2 stores constraints in metadata
    for meta in getattr(field, "metadata", []) or []:
        if hasattr(meta, "gt"):
            constraints["gt"] = getattr(meta, "gt", None)
        if hasattr(meta, "ge"):
            constraints["ge"] = getattr(meta, "ge", None)
        if hasattr(meta, "lt"):
            constraints["lt"] = getattr(meta, "lt", None)
        if hasattr(meta, "le"):
            constraints["le"] = getattr(meta, "le", None)
        if hasattr(meta, "min_length"):
            constraints["min_length"] = getattr(meta, "min_length", None)
        if hasattr(meta, "max_length"):
            constraints["max_length"] = getattr(meta, "max_length", None)
    return constraints
