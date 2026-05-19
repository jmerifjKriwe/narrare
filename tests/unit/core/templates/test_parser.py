"""Unit tests for template parser — v2 backward compat, v1, sections, edge cases.

Tests cover:
- parse_template with v2 grouped format (backward compat — language ignored)
- parse_template with v1 flat format (backward compat)
- Sections parsing independently
- Field groups flattening into fields list
- Empty/missing frontmatter still works
"""

from __future__ import annotations

from narrare_core.templates.models import TemplateFieldGroup
from narrare_core.templates.parser import parse_template


class TestParseTemplateV2BackwardCompat:
    """Backward compatibility: v2 templates with template_language still parse."""

    V2_TEMPLATE = """---
template_type: character
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    fields:
      age:
        type: int
        description: Character age
      role:
        type: str
        required: true
  appearance:
    label_key: kb.groups.appearance
    fields:
      height:
        type: str
        description: Physical height
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

    def test_parses_meta_ignores_language(self) -> None:
        """template_language in v2 frontmatter is silently ignored."""
        template = parse_template(self.V2_TEMPLATE)
        assert template.meta.template_type == "character"
        assert template.meta.template_version == "2.0.0"
        assert template.meta.schema_version == "2.0.0"
        assert not hasattr(template.meta, "template_language")

    def test_preserves_field_descriptions(self) -> None:
        """V2 field descriptions are preserved for backward compat."""
        template = parse_template(self.V2_TEMPLATE)
        age_field = next(f for f in template.fields if f.name == "age")
        assert age_field.description == "Character age"

        height_field = next(f for f in template.fields if f.name == "height")
        assert height_field.description == "Physical height"

    def test_parses_field_groups(self) -> None:
        template = parse_template(self.V2_TEMPLATE)
        assert len(template.field_groups) == 2

        basic_info = template.field_groups[0]
        assert isinstance(basic_info, TemplateFieldGroup)
        assert basic_info.name == "basic_info"
        assert basic_info.label_key == "kb.groups.basicInfo"
        assert len(basic_info.fields) == 2

        appearance = template.field_groups[1]
        assert appearance.name == "appearance"
        assert appearance.label_key == "kb.groups.appearance"
        assert len(appearance.fields) == 1
        assert appearance.fields[0].name == "height"

    def test_flattens_fields_from_groups(self) -> None:
        template = parse_template(self.V2_TEMPLATE)
        assert len(template.fields) == 3  # age, role, height

    def test_parses_sections(self) -> None:
        template = parse_template(self.V2_TEMPLATE)
        assert len(template.sections) == 2

    def test_body_content(self) -> None:
        template = parse_template(self.V2_TEMPLATE)
        assert "# Character Template" in template.body


class TestParseTemplateV1BackwardCompat:
    """Backward compatibility: v1 flat format still works identically."""

    V1_TEMPLATE = """---
template_type: character
template_version: "1.0.0"
template_language: en
schema_version: "1.0.0"
age:
  type: int
  description: Character age
role:
  type: str
  required: true
aliases:
  type: list
  description: Known aliases
---

# Character Template
"""

    def test_parses_meta_ignores_language(self) -> None:
        """template_language in v1 frontmatter is silently ignored."""
        template = parse_template(self.V1_TEMPLATE)
        assert template.meta.template_type == "character"
        assert template.meta.template_version == "1.0.0"
        assert not hasattr(template.meta, "template_language")

    def test_parses_flat_fields(self) -> None:
        template = parse_template(self.V1_TEMPLATE)
        assert len(template.fields) == 3

        age_field = next(f for f in template.fields if f.name == "age")
        assert age_field.field_type == "int"
        assert age_field.description == "Character age"

        role_field = next(f for f in template.fields if f.name == "role")
        assert role_field.required is True

    def test_no_field_groups_in_v1(self) -> None:
        template = parse_template(self.V1_TEMPLATE)
        assert template.field_groups == []

    def test_no_sections_in_v1(self) -> None:
        template = parse_template(self.V1_TEMPLATE)
        assert template.sections == []


class TestParseTemplateSectionsOnly:
    """Templates can have sections without field_groups."""

    SECTIONS_ONLY = """---
template_type: character
template_version: "1.0.0"
schema_version: "1.0.0"
sections:
  background:
    label_key: kb.sections.background
    order: 1
---

# Body
"""

    def test_parses_sections_without_groups(self) -> None:
        template = parse_template(self.SECTIONS_ONLY)
        assert len(template.sections) == 1
        assert template.sections[0].name == "background"
        assert template.field_groups == []

    def test_still_parses_flat_fields_when_no_groups(self) -> None:
        template = parse_template(self.SECTIONS_ONLY)
        assert template.fields == []


class TestParseTemplateGroupsExtraFields:
    """Group field models should accept extra fields (extra='allow')."""

    V2_WITH_EXTRA = """---
template_type: character
template_version: "2.0.0"
schema_version: "2.0.0"
field_groups:
  custom_group:
    label_key: custom.label
    custom_meta: some_value
    fields:
      custom_field:
        type: str
        description: A custom field
        extra_prop: true
---

# Body
"""

    def test_group_with_extra_meta(self) -> None:
        template = parse_template(self.V2_WITH_EXTRA)
        assert len(template.field_groups) == 1
        assert template.field_groups[0].name == "custom_group"
        assert template.field_groups[0].label_key == "custom.label"

    def test_field_with_extra_props(self) -> None:
        template = parse_template(self.V2_WITH_EXTRA)
        assert len(template.fields) == 1
        assert template.fields[0].name == "custom_field"
        assert template.fields[0].description == "A custom field"


class TestParseTemplateEdgeCases:
    """Edge cases: empty, missing frontmatter, etc."""

    def test_missing_frontmatter(self) -> None:
        template = parse_template("# Just content")
        assert template.meta.template_type == ""
        assert template.fields == []
        assert template.field_groups == []
        assert template.sections == []

    def test_empty_string(self) -> None:
        template = parse_template("")
        assert template.meta.template_type == ""
        assert template.fields == []
        assert template.field_groups == []
        assert template.sections == []

    def test_v1_simple_key_value(self) -> None:
        template = parse_template("---\ntemplate_type: object\nowner: someone\n---\nBody.\n")
        owner_field = next(f for f in template.fields if f.name == "owner")
        assert owner_field.field_type == "str"

    def test_v2_no_fields_in_group(self) -> None:
        raw = """---
template_type: character
template_version: "2.0.0"
field_groups:
  empty_group:
    label_key: empty
    fields: {}
---

# Body
"""
        template = parse_template(raw)
        assert len(template.field_groups) == 1
        assert template.field_groups[0].fields == []
        assert template.fields == []

    def test_v2_group_with_non_dict_value(self) -> None:
        raw = """---
template_type: character
template_version: "2.0.0"
field_groups:
  valid_group:
    label_key: valid
    fields:
      age:
        type: int
  invalid_group: just_a_string
---

# Body
"""
        template = parse_template(raw)
        assert len(template.field_groups) == 1
        assert template.field_groups[0].name == "valid_group"

    def test_v2_section_with_non_dict_value(self) -> None:
        raw = """---
template_type: character
template_version: "2.0.0"
sections:
  background: plain_string
---

# Body
"""
        template = parse_template(raw)
        assert len(template.sections) == 1
        assert template.sections[0].name == "background"
        assert template.sections[0].label_key == ""
        assert template.sections[0].order == 0
