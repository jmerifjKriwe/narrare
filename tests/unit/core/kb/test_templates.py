"""Unit tests for the template system.

Tests cover:
- parse_template with valid template (character.md)
- parse_template with missing frontmatter
- parse_template with empty string
- Defaults loading for en/de/fr
- Defaults fallback to en
- schema_bridge get_form_fields for character
- schema_bridge validate_metadata valid and invalid
- TemplateField, TemplateMeta, Template models
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.templates.defaults import (
    list_default_templates,
    load_default_template,
)
from narrare_core.templates.models import Template, TemplateField, TemplateMeta
from narrare_core.templates.parser import parse_template
from narrare_core.templates.schema_bridge import get_form_fields, validate_metadata

# ---------------------------------------------------------------------------
# TemplateField model
# ---------------------------------------------------------------------------


class TestTemplateField:
    """Tests for the TemplateField Pydantic model."""

    def test_defaults(self) -> None:
        field = TemplateField(name="age")
        assert field.name == "age"
        assert field.field_type == "str"
        assert field.required is False
        assert field.description == ""

    def test_all_fields(self) -> None:
        field = TemplateField(
            name="role",
            field_type="str",
            required=True,
            description="Character role",
        )
        assert field.name == "role"
        assert field.required is True
        assert field.description == "Character role"

    def test_int_type(self) -> None:
        field = TemplateField(name="age", field_type="int")
        assert field.field_type == "int"


# ---------------------------------------------------------------------------
# TemplateMeta model
# ---------------------------------------------------------------------------


class TestTemplateMeta:
    """Tests for the TemplateMeta Pydantic model."""

    def test_defaults(self) -> None:
        meta = TemplateMeta(template_type="character")
        assert meta.template_type == "character"
        assert meta.template_version == "1.0.0"
        assert meta.template_language == "en"
        assert meta.schema_version == "1.0.0"

    def test_all_fields(self) -> None:
        meta = TemplateMeta(
            template_type="location",
            template_version="2.0.0",
            template_language="de",
            schema_version="1.1.0",
        )
        assert meta.template_language == "de"
        assert meta.template_version == "2.0.0"


# ---------------------------------------------------------------------------
# Template model
# ---------------------------------------------------------------------------


class TestTemplate:
    """Tests for the Template Pydantic model."""

    def test_minimal(self) -> None:
        template = Template(
            meta=TemplateMeta(template_type="character"),
            fields=[],
        )
        assert template.meta.template_type == "character"
        assert template.fields == []
        assert template.body == ""
        assert template.raw == ""

    def test_full(self) -> None:
        template = Template(
            meta=TemplateMeta(template_type="character"),
            fields=[TemplateField(name="age", field_type="int")],
            body="# Character",
            raw="---\n---\n# Character",
        )
        assert len(template.fields) == 1
        assert template.body == "# Character"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParseTemplate:
    """Tests for the parse_template function."""

    def test_valid_character_template(self) -> None:
        """Parsing a valid character template should extract meta + fields."""
        raw = (
            "---\n"
            "template_type: character\n"
            "template_version: '1.0.0'\n"
            "template_language: en\n"
            "schema_version: '1.0.0'\n"
            "age:\n"
            "  type: int\n"
            "  description: Character age\n"
            "role:\n"
            "  type: str\n"
            "  required: true\n"
            "---\n"
            "\n"
            "# Character Template\n"
            "\n"
            "Use this template.\n"
        )
        template = parse_template(raw)

        assert template.meta.template_type == "character"
        assert template.meta.template_version == "1.0.0"
        assert template.meta.template_language == "en"
        assert template.raw == raw

        # Should have 2 fields (age and role)
        assert len(template.fields) == 2

        age_field = next(f for f in template.fields if f.name == "age")
        assert age_field.field_type == "int"
        assert age_field.description == "Character age"
        assert age_field.required is False

        role_field = next(f for f in template.fields if f.name == "role")
        assert role_field.field_type == "str"
        assert role_field.required is True

        assert "# Character Template" in template.body

    def test_missing_frontmatter(self) -> None:
        """Content without frontmatter should become body with empty meta."""
        raw = "# Just a heading\n\nSome content."
        template = parse_template(raw)

        assert template.meta.template_type == ""
        assert template.fields == []
        assert "# Just a heading" in template.body

    def test_empty_string(self) -> None:
        """Empty string should produce empty template."""
        template = parse_template("")

        assert template.meta.template_type == ""
        assert template.fields == []
        assert template.body == ""

    def test_simple_key_value_fields(self) -> None:
        """Simple key:value frontmatter entries should become fields."""
        raw = "---\ntemplate_type: object\nowner: someone\n---\nBody text.\n"
        template = parse_template(raw)

        assert template.meta.template_type == "object"
        owner_field = next(f for f in template.fields if f.name == "owner")
        assert owner_field.field_type == "str"
        assert owner_field.required is False

    def test_list_type_field(self) -> None:
        """Fields with type: list should map to list[str]."""
        raw = (
            "---\n"
            "template_type: faction\n"
            "members:\n"
            "  type: list\n"
            "  description: Faction members\n"
            "---\n"
            "Body.\n"
        )
        template = parse_template(raw)

        members_field = next(f for f in template.fields if f.name == "members")
        assert members_field.field_type == "list[str]"


# ---------------------------------------------------------------------------
# Defaults loading
# ---------------------------------------------------------------------------


class TestDefaultTemplates:
    """Tests for loading bundled default templates."""

    @pytest.mark.parametrize("language", ["en", "de", "fr"])
    @pytest.mark.parametrize(
        "entity_type",
        ["character", "location", "faction", "object", "system", "timeline"],
    )
    def test_all_entity_types_all_languages(
        self,
        entity_type: str,
        language: str,
    ) -> None:
        """Every entity type should have a template in every language."""
        content = load_default_template(entity_type, language)
        assert content is not None
        assert entity_type in content

    def test_fallback_to_english(self) -> None:
        """Non-existent language should fall back to English."""
        # "xx" doesn't exist — should get the English version
        content = load_default_template("character", "xx")
        assert content is not None
        assert "Character" in content  # English template has "Character"

    def test_unknown_entity_type_returns_none(self) -> None:
        """Unknown entity type should return None."""
        content = load_default_template("unknown_type", "en")
        assert content is None

    def test_list_default_templates(self) -> None:
        """Should list all 6 entity types x 3 languages = 18 templates."""
        templates = list_default_templates()
        assert len(templates) == 18

        # All entity types present
        entity_types = {t[0] for t in templates}
        assert entity_types == {"character", "location", "faction", "object", "system", "timeline"}

        # All languages present
        languages = {t[1] for t in templates}
        assert languages == {"en", "de", "fr"}

    def test_character_template_parseable(self) -> None:
        """The English character template should parse correctly."""
        raw = load_default_template("character", "en")
        assert raw is not None

        template = parse_template(raw)
        assert template.meta.template_type == "character"
        assert len(template.fields) == 11  # 11 character fields


# ---------------------------------------------------------------------------
# Schema bridge
# ---------------------------------------------------------------------------


class TestSchemaBridgeGetFormFields:
    """Tests for get_form_fields."""

    def test_character_fields(self) -> None:
        """Character should return template fields."""
        fields = get_form_fields("character")
        assert len(fields) > 0

        field_names = {f.name for f in fields}
        assert "age" in field_names
        assert "role" in field_names
        assert "aliases" in field_names

    def test_unknown_entity_type_returns_empty(self) -> None:
        """Unknown entity type should return empty list."""
        fields = get_form_fields("nonexistent")
        assert fields == []

    @pytest.mark.parametrize(
        "entity_type",
        ["character", "location", "faction", "object", "system", "timeline"],
    )
    def test_all_known_types_have_fields(self, entity_type: str) -> None:
        """All known entity types should have template fields."""
        fields = get_form_fields(entity_type)
        assert len(fields) > 0


class TestSchemaBridgeValidateMetadata:
    """Tests for validate_metadata."""

    def test_valid_character_metadata(self) -> None:
        """Valid character metadata should pass validation."""
        result = validate_metadata(
            "character",
            {
                "age": 30,
                "role": "protagonist",
                "aliases": ["Hero"],
            },
        )
        assert result is not None

    def test_invalid_character_age(self) -> None:
        """Non-integer age should fail validation."""
        with pytest.raises(ValidationError):
            validate_metadata("character", {"age": "not a number"})

    def test_empty_metadata_valid(self) -> None:
        """Empty metadata should pass (all fields optional)."""
        result = validate_metadata("character", {})
        assert result is not None

    def test_extra_fields_preserved(self) -> None:
        """Extra fields should be preserved."""
        result = validate_metadata("character", {"custom": "value"})
        dumped = result.model_dump()
        assert dumped["custom"] == "value"

    def test_unknown_entity_type_uses_base(self) -> None:
        """Unknown entity type should use base schema (extra="allow")."""
        result = validate_metadata("custom_type", {"anything": "goes"})
        dumped = result.model_dump()
        assert dumped["anything"] == "goes"
