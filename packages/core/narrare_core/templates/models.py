"""Pydantic models for the template system.

Defines the data structures used to represent entity-type templates,
including their metadata (type, version, language) and field definitions.
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


class TemplateMeta(BaseModel):
    """Metadata extracted from a template's YAML frontmatter."""

    template_type: str
    template_version: str = "1.0.0"
    template_language: str = "en"
    schema_version: str = "1.0.0"


class Template(BaseModel):
    """A complete entity-type template with metadata, fields, and body.

    Parsed from Markdown + YAML frontmatter files.  The ``fields`` list
    describes recommended metadata fields; ``body`` is the Markdown
    template content for display or further processing.
    """

    meta: TemplateMeta
    fields: list[TemplateField]
    body: str = ""
    raw: str = ""
