"""Template parser — parses Markdown + YAML frontmatter into Template models.

Uses the shared ``parse_frontmatter`` utility so that template parsing
is consistent with the rest of the application's frontmatter handling.

Supports two frontmatter formats:

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
"""

from __future__ import annotations

from typing import Any

from narrare_core.shared.frontmatter import parse_frontmatter

from .models import Template, TemplateField, TemplateFieldGroup, TemplateMeta, TemplateSection

# Frontmatter keys that map to TemplateMeta fields
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
            fields.append(_parse_field_entry(key, value))  # type: ignore[reportUnknownArgumentType]
        else:
            # Simple key: value → field with default type
            fields.append(TemplateField(name=key))
    return fields


def _parse_field_groups(metadata: dict[str, Any]) -> list[TemplateFieldGroup]:
    """Parse ``field_groups`` from v2 frontmatter.

    Returns a list of ``TemplateFieldGroup`` objects extracted from the
    ``field_groups`` top-level key, which is a dict of group-name → group-def.
    """
    groups_data = metadata.get("field_groups", {})
    if not isinstance(groups_data, dict):
        return []

    groups: list[TemplateFieldGroup] = []
    for group_name, group_def in groups_data.items():  # type: ignore[reportUnknownVariableType]
        if not isinstance(group_def, dict):
            continue
        label_key = str(group_def.get("label_key", ""))  # type: ignore[reportUnknownMemberType]
        description_key = str(group_def.get("description_key", ""))  # type: ignore[reportUnknownMemberType]
        order = int(group_def.get("order", 0))  # type: ignore[reportUnknownMemberType]

        fields_data = group_def.get("fields", {})  # type: ignore[reportUnknownMemberType]
        fields: list[TemplateField] = []
        if isinstance(fields_data, dict):
            for field_name, field_def in fields_data.items():  # type: ignore[reportUnknownVariableType]
                if isinstance(field_def, dict):
                    fields.append(_parse_field_entry(field_name, field_def))  # type: ignore[reportUnknownArgumentType]
                else:
                    fields.append(TemplateField(name=field_name))  # type: ignore[reportUnknownArgumentType]

        groups.append(
            TemplateFieldGroup(
                name=group_name,  # type: ignore[reportUnknownArgumentType]
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
    sections_data = metadata.get("sections", {})
    if not isinstance(sections_data, dict):
        return []

    sections: list[TemplateSection] = []
    for section_name, section_def in sections_data.items():  # type: ignore[reportUnknownVariableType]
        if not isinstance(section_def, dict):
            sections.append(TemplateSection(name=section_name))  # type: ignore[reportUnknownArgumentType]
            continue
        sections.append(
            TemplateSection(
                name=section_name,  # type: ignore[reportUnknownArgumentType]
                label_key=str(section_def.get("label_key", "")),  # type: ignore[reportUnknownMemberType]
                description_key=str(section_def.get("description_key", "")),  # type: ignore[reportUnknownMemberType]
                order=int(section_def.get("order", 0)),  # type: ignore[reportUnknownMemberType]
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
        template_language=metadata.get("template_language", "en"),
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
