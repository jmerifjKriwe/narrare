"""Unit tests for template parser — v3 language-neutral format.

Tests cover:
- parse_template with v3 grouped format (no language, no field descriptions)
- Field groups flattening into fields list
- Sections parsing with v3 templates
- V3-specific edge cases
"""

from __future__ import annotations

from narrare_core.templates.models import TemplateFieldGroup, TemplateSection
from narrare_core.templates.parser import parse_template


class TestParseTemplateV3:
    """Tests for v3 language-neutral grouped frontmatter format."""

    V3_TEMPLATE = """---
template_type: character
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      age:
        type: int
      role:
        type: str
        required: true
  appearance:
    label_key: kb.groups.appearance
    description_key: kb.groups.appearanceHint
    order: 2
    fields:
      height:
        type: str
sections:
  background:
    label_key: kb.sections.background
    description_key: kb.sections.backgroundHint
    order: 1
  personality:
    label_key: kb.sections.personality
    description_key: kb.sections.personalityHint
    order: 2
---

# Character Template

Body content.
"""

    def test_parses_meta_without_language(self) -> None:
        template = parse_template(self.V3_TEMPLATE)
        assert template.meta.template_type == "character"
        assert template.meta.template_version == "3.0.0"
        assert template.meta.schema_version == "2.0.0"
        assert not hasattr(template.meta, "template_language")

    def test_field_descriptions_are_empty(self) -> None:
        """V3 fields have no description — display text comes from i18n."""
        template = parse_template(self.V3_TEMPLATE)
        for field in template.fields:
            assert field.description == ""

    def test_parses_field_groups(self) -> None:
        template = parse_template(self.V3_TEMPLATE)
        assert len(template.field_groups) == 2

        basic_info = template.field_groups[0]
        assert isinstance(basic_info, TemplateFieldGroup)
        assert basic_info.name == "basic_info"
        assert basic_info.label_key == "kb.groups.basicInfo"
        assert basic_info.description_key == "kb.groups.basicInfoHint"
        assert basic_info.order == 1
        assert len(basic_info.fields) == 2

        appearance = template.field_groups[1]
        assert appearance.name == "appearance"
        assert appearance.label_key == "kb.groups.appearance"
        assert len(appearance.fields) == 1
        assert appearance.fields[0].name == "height"

    def test_flattens_fields_from_groups(self) -> None:
        template = parse_template(self.V3_TEMPLATE)
        assert len(template.fields) == 3  # age, role, height

        field_names = {f.name for f in template.fields}
        assert "age" in field_names
        assert "role" in field_names
        assert "height" in field_names

    def test_preserves_field_types(self) -> None:
        template = parse_template(self.V3_TEMPLATE)
        age_field = next(f for f in template.fields if f.name == "age")
        assert age_field.field_type == "int"

        role_field = next(f for f in template.fields if f.name == "role")
        assert role_field.field_type == "str"
        assert role_field.required is True

    def test_parses_sections(self) -> None:
        template = parse_template(self.V3_TEMPLATE)
        assert len(template.sections) == 2

        bg = template.sections[0]
        assert isinstance(bg, TemplateSection)
        assert bg.name == "background"
        assert bg.label_key == "kb.sections.background"
        assert bg.description_key == "kb.sections.backgroundHint"
        assert bg.order == 1

        pers = template.sections[1]
        assert pers.name == "personality"
        assert pers.order == 2

    def test_body_content(self) -> None:
        template = parse_template(self.V3_TEMPLATE)
        assert "# Character Template" in template.body
        assert "Body content." in template.body

    def test_raw_preserved(self) -> None:
        template = parse_template(self.V3_TEMPLATE)
        assert template.raw == self.V3_TEMPLATE

    def test_v3_field_without_description_key(self) -> None:
        """V3 fields omit description entirely — parser creates empty string."""
        raw = """---
template_type: character
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    fields:
      age:
        type: int
---

# Body
"""
        template = parse_template(raw)
        age_field = next(f for f in template.fields if f.name == "age")
        assert age_field.field_type == "int"
        assert age_field.description == ""
