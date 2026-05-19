"""Pydantic models for the template system.

Defines the data structures used to represent entity-type templates,
including their metadata (type, version, language), field definitions,
grouped metadata fields, and guided body text sections.
"""

from __future__ import annotations

from pydantic import BaseModel


class TemplateField(BaseModel):
    """A single field definition in a template.

    Describes a metadata field that the template recommends for an
    entity type.  Not enforced — templates are suggestions.
    """

    name: str
    field_type: str = "str"
    required: bool = False
    description: str = ""


class TemplateSection(BaseModel):
    """A guided body text section for an entity type.

    Sections like "Background", "Personality" with a placeholder hint.
    """

    name: str
    label_key: str = ""
    description_key: str = ""
    order: int = 0


class TemplateFieldGroup(BaseModel):
    """A named group of related metadata fields.

    Groups like "Grundinformationen", "Erscheinung", "Persönlichkeit".
    """

    name: str
    label_key: str = ""
    description_key: str = ""
    fields: list[TemplateField] = []
    order: int = 0


class TemplateMeta(BaseModel):
    """Metadata extracted from a template's YAML frontmatter."""

    template_type: str
    template_version: str = "1.0.0"
    template_language: str = "en"
    schema_version: str = "1.0.0"


class Template(BaseModel):
    """A complete entity-type template with metadata, fields, and body.

    Parsed from Markdown + YAML frontmatter files.  The ``fields`` list
    describes recommended metadata fields (kept for backward compat);
    ``field_groups`` and ``sections`` provide richer structure for
    the v2 template format.
    """

    meta: TemplateMeta
    fields: list[TemplateField] = []
    field_groups: list[TemplateFieldGroup] = []
    sections: list[TemplateSection] = []
    body: str = ""
    raw: str = ""
