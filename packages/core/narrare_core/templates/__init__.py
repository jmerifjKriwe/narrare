"""Template system for entity-type templates.

Provides parsing, default template access, and schema bridging.
The ``TemplateResolver`` protocol is defined in ``contracts.py`` for
implementations in the API layer.

Public exports:
    TemplateField — Single field definition in a template
    TemplateFieldGroup — Group of related metadata fields
    TemplateMeta — Template metadata (type, version, language)
    TemplateSection — Guided body text section
    Template — Complete parsed template
    TemplateResolver — Protocol for template resolution
    parse_template — Parse Markdown+YAML frontmatter into Template
    load_default_template — Load a bundled default template
    list_default_templates — List all available bundled templates
    get_form_fields — Get template fields for an entity type
    validate_metadata — Validate metadata dict against entity schema
"""

from .contracts import TemplateResolver
from .defaults import list_default_templates, load_default_template
from .models import Template, TemplateField, TemplateFieldGroup, TemplateMeta, TemplateSection
from .parser import parse_template
from .schema_bridge import get_form_fields, validate_metadata

__all__ = [
    "Template",
    "TemplateField",
    "TemplateFieldGroup",
    "TemplateMeta",
    "TemplateResolver",
    "TemplateSection",
    "get_form_fields",
    "list_default_templates",
    "load_default_template",
    "parse_template",
    "validate_metadata",
]
