"""Template parser — parses Markdown + YAML frontmatter into Template models.

Uses the shared ``parse_frontmatter`` utility so that template parsing
is consistent with the rest of the application's frontmatter handling.

Supports three frontmatter formats:

**v1 (flat):**:

    ---
    template_type: character
    template_version: "1.0.0"
    age:
      type: int
      description: Character age
    ---

**v2 (grouped):**:

    ---
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
    sections:
      background:
        label_key: kb.sections.background
        order: 1
    ---

**v3 (language-neutral):**:

    ---
    template_type: character
    template_version: "3.0.0"
    schema_version: "2.0.0"
    field_groups:
      basic_info:
        label_key: kb.groups.basicInfo
        fields:
          age:
            type: int
    sections:
      background:
        label_key: kb.sections.background
        order: 1
    ---

Legacy ``template_language`` keys in v2 templates are silently ignored.
"""

from __future__ import annotations

from typing import Any, cast

from narrare_core.shared.frontmatter import parse_frontmatter

from .models import Template, TemplateField, TemplateFieldGroup, TemplateMeta, TemplateSection

# Frontmatter keys that map to TemplateMeta fields (or are silently
# ignored for backward compatibility, e.g. ``template_language``).
_META_KEYS = frozenset(
    {
        "template_type",
        "template_version",
        "template_language",
        "schema_version",
    }
)

# Structured keys parsed separately (not flat fields)
_STRUCTURED_KEYS = frozenset({"field_groups", "sections"})

# Type hint strings in frontmatter that map to Python types
_TYPE_MAP: dict[str, str] = {
    "str": "str",
    "int": "int",
    "bool": "bool",
    "float": "float",
    "list": "list[str]",
    "list[str]": "list[str]",
}


def _parse_field_entry(key: str, value: dict[str, Any]) -> TemplateField:
    """Parse a single field definition from a frontmatter dict entry."""
    field_type_raw = str(value.get("type", "str"))
    field_required_raw = value.get("required", False)
    field_desc_raw = value.get("description", "")
    return TemplateField(
        name=key,
        field_type=_TYPE_MAP.get(field_type_raw, "str"),
        required=bool(field_required_raw),
        description=str(field_desc_raw),
    )


def _parse_flat_fields(metadata: dict[str, Any]) -> list[TemplateField]:
    """Parse flat (v1) field definitions from frontmatter metadata.

    All keys that are not in ``_META_KEYS`` or ``_STRUCTURED_KEYS``
    are treated as field definitions.
    """
    fields: list[TemplateField] = []
    for key, value in metadata.items():
        if key in _META_KEYS or key in _STRUCTURED_KEYS:
            continue
        if isinstance(value, dict):
            fields.append(_parse_field_entry(key, cast("dict[str, Any]", value)))
        else:
            # Simple key: value → field with default type
            fields.append(TemplateField(name=key))
    return fields


def _parse_field_groups(metadata: dict[str, Any]) -> list[TemplateFieldGroup]:
    """Parse ``field_groups`` from v2 frontmatter.

    Returns a list of ``TemplateFieldGroup`` objects extracted from the
    ``field_groups`` top-level key, which is a dict of group-name → group-def.
    """
    groups_data_raw = metadata.get("field_groups", {})
    if not isinstance(groups_data_raw, dict):
        return []

    groups_data: dict[str, Any] = cast("dict[str, Any]", groups_data_raw)
    groups: list[TemplateFieldGroup] = []
    for group_name, group_def in groups_data.items():
        if not isinstance(group_def, dict):
            continue
        group_def_typed: dict[str, Any] = cast("dict[str, Any]", group_def)
        label_key = str(group_def_typed.get("label_key", ""))
        description_key = str(group_def_typed.get("description_key", ""))
        order = int(group_def_typed.get("order", 0))

        fields_data_raw = group_def_typed.get("fields", {})
        fields: list[TemplateField] = []
        if isinstance(fields_data_raw, dict):
            fields_data: dict[str, Any] = cast("dict[str, Any]", fields_data_raw)
            for field_name, field_def in fields_data.items():
                if isinstance(field_def, dict):
                    fields.append(_parse_field_entry(field_name, cast("dict[str, Any]", field_def)))
                else:
                    fields.append(TemplateField(name=str(field_name)))

        groups.append(
            TemplateFieldGroup(
                name=str(group_name),
                label_key=label_key,
                description_key=description_key,
                fields=fields,
                order=order,
            )
        )
    return groups


def _flatten_fields_from_groups(groups: list[TemplateFieldGroup]) -> list[TemplateField]:
    """Flatten all fields from a list of field groups into a single list."""
    result: list[TemplateField] = []
    for group in groups:
        result.extend(group.fields)
    return result


def _parse_sections(metadata: dict[str, Any]) -> list[TemplateSection]:
    """Parse ``sections`` from v2 frontmatter.

    Returns a list of ``TemplateSection`` objects extracted from the
    ``sections`` top-level key, which is a dict of section-name → section-def.
    """
    sections_data_raw = metadata.get("sections", {})
    if not isinstance(sections_data_raw, dict):
        return []

    sections_data: dict[str, Any] = cast("dict[str, Any]", sections_data_raw)
    sections: list[TemplateSection] = []
    for section_name, section_def in sections_data.items():
        if not isinstance(section_def, dict):
            sections.append(TemplateSection(name=str(section_name)))
            continue
        section_def_typed: dict[str, Any] = cast("dict[str, Any]", section_def)
        sections.append(
            TemplateSection(
                name=str(section_name),
                label_key=str(section_def_typed.get("label_key", "")),
                description_key=str(section_def_typed.get("description_key", "")),
                order=int(section_def_typed.get("order", 0)),
            )
        )
    return sections


def parse_template(raw: str) -> Template:
    """Parse a Markdown + YAML frontmatter string into a Template.

    Supports v1 (flat fields) and v2 (grouped fields + sections) formats.
    v2 frontmatter is detected by the presence of a ``field_groups`` key.
    When v2 format is used, fields are flattened from all groups into the
    ``fields`` list for backward compatibility.

    If no frontmatter is present, the entire content becomes ``body``
    with empty metadata.

    Args:
        raw: Raw Markdown content with optional YAML frontmatter.

    Returns:
        A Template with parsed meta, fields, groups, sections, body,
        and the original raw text.
    """
    parsed = parse_frontmatter(raw)
    metadata = parsed.metadata

    # Extract meta fields
    meta = TemplateMeta(
        template_type=metadata.get("template_type", ""),
        template_version=metadata.get("template_version", "1.0.0"),
        schema_version=metadata.get("schema_version", "1.0.0"),
    )

    # Detect v2 vs v1 format
    has_groups = "field_groups" in metadata and isinstance(metadata["field_groups"], dict)

    if has_groups:
        # v2 grouped format
        field_groups = _parse_field_groups(metadata)
        fields = _flatten_fields_from_groups(field_groups)
        sections = _parse_sections(metadata)
    else:
        # v1 flat format
        fields = _parse_flat_fields(metadata)
        field_groups = []
        sections = _parse_sections(metadata)  # sections can appear standalone

    return Template(
        meta=meta,
        fields=fields,
        field_groups=field_groups,
        sections=sections,
        body=parsed.content,
        raw=raw,
    )
