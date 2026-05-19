"""Unit tests for template models — TemplateSection, TemplateFieldGroup, Template.

Tests cover:
- TemplateSection defaults and construction
- TemplateFieldGroup defaults and construction
- Template model with new field_groups and sections fields
- Template backward compatibility (fields list still works)
- extra="allow" on group models (via default Pydantic behaviour)
"""

from __future__ import annotations

from narrare_core.templates.models import (
    Template,
    TemplateField,
    TemplateFieldGroup,
    TemplateMeta,
    TemplateSection,
)


class TestTemplateSection:
    """Tests for the TemplateSection Pydantic model."""

    def test_minimal(self) -> None:
        section = TemplateSection(name="background")
        assert section.name == "background"
        assert section.label_key == ""
        assert section.description_key == ""
        assert section.order == 0

    def test_full(self) -> None:
        section = TemplateSection(
            name="background",
            label_key="kb.sections.background",
            description_key="kb.sections.backgroundHint",
            order=2,
        )
        assert section.name == "background"
        assert section.label_key == "kb.sections.background"
        assert section.description_key == "kb.sections.backgroundHint"
        assert section.order == 2


class TestTemplateFieldGroup:
    """Tests for the TemplateFieldGroup Pydantic model."""

    def test_minimal(self) -> None:
        group = TemplateFieldGroup(name="basic_info")
        assert group.name == "basic_info"
        assert group.label_key == ""
        assert group.description_key == ""
        assert group.fields == []
        assert group.order == 0

    def test_with_fields(self) -> None:
        group = TemplateFieldGroup(
            name="appearance",
            label_key="kb.groups.appearance",
            fields=[
                TemplateField(name="height", field_type="str"),
                TemplateField(name="hair_color", field_type="str"),
            ],
            order=1,
        )
        assert group.name == "appearance"
        assert len(group.fields) == 2
        assert group.fields[0].name == "height"
        assert group.order == 1

    def test_empty_fields_by_default(self) -> None:
        group = TemplateFieldGroup(name="empty_group")
        assert group.fields == []


class TestTemplateExtended:
    """Tests for the Template model with new field_groups and sections."""

    def test_minimal(self) -> None:
        template = Template(meta=TemplateMeta(template_type="character"))
        assert template.meta.template_type == "character"
        assert template.fields == []
        assert template.field_groups == []
        assert template.sections == []
        assert template.body == ""
        assert template.raw == ""

    def test_with_fields_list(self) -> None:
        """Backward compat: fields list still works directly."""
        template = Template(
            meta=TemplateMeta(template_type="character"),
            fields=[TemplateField(name="age", field_type="int")],
        )
        assert len(template.fields) == 1

    def test_with_field_groups(self) -> None:
        template = Template(
            meta=TemplateMeta(template_type="character"),
            field_groups=[
                TemplateFieldGroup(
                    name="basic_info",
                    fields=[TemplateField(name="age")],
                ),
            ],
        )
        assert len(template.field_groups) == 1
        assert template.field_groups[0].name == "basic_info"

    def test_with_sections(self) -> None:
        template = Template(
            meta=TemplateMeta(template_type="character"),
            sections=[
                TemplateSection(name="background", order=1),
                TemplateSection(name="personality", order=2),
            ],
        )
        assert len(template.sections) == 2
        assert template.sections[1].name == "personality"

    def test_full_template(self) -> None:
        template = Template(
            meta=TemplateMeta(template_type="character"),
            fields=[TemplateField(name="age")],
            field_groups=[
                TemplateFieldGroup(
                    name="basic_info",
                    fields=[TemplateField(name="age")],
                ),
            ],
            sections=[TemplateSection(name="background", order=1)],
            body="# Character",
            raw="---\n---\n# Character",
        )
        assert len(template.fields) == 1
        assert len(template.field_groups) == 1
        assert len(template.sections) == 1
