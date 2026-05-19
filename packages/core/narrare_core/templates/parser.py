"""Template parser — parses Markdown + YAML frontmatter into Template models.

Uses the shared ``parse_frontmatter`` utility so that template parsing
is consistent with the rest of the application's frontmatter handling.
"""

from __future__ import annotations

from narrare_core.shared.frontmatter import parse_frontmatter

from .models import Template, TemplateField, TemplateMeta

# Frontmatter keys that map to TemplateMeta fields
_META_KEYS = frozenset(
    {
        "template_type",
        "template_version",
        "template_language",
        "schema_version",
    }
)

# Type hint strings in frontmatter that map to Python types
_TYPE_MAP: dict[str, str] = {
    "str": "str",
    "int": "int",
    "bool": "bool",
    "float": "float",
    "list": "list[str]",
    "list[str]": "list[str]",
}


def parse_template(raw: str) -> Template:
    """Parse a Markdown + YAML frontmatter string into a Template.

    Frontmatter format::

        ---
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
        ---

        # Character Template

        Body content here.

    If no frontmatter is present, the entire content becomes ``body``
    with empty metadata.

    Args:
        raw: Raw Markdown content with optional YAML frontmatter.

    Returns:
        A Template with parsed meta, fields, body, and the original raw text.
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

    # Build fields from remaining frontmatter keys
    fields: list[TemplateField] = []
    for key, value in metadata.items():
        if key in _META_KEYS:
            continue

        if isinstance(value, dict):
            field_type_raw = str(value.get("type", "str"))  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            field_required_raw = value.get("required", False)  # type: ignore[reportUnknownMemberType]
            field_desc_raw = value.get("description", "")  # type: ignore[reportUnknownMemberType]
            fields.append(
                TemplateField(
                    name=key,
                    field_type=_TYPE_MAP.get(field_type_raw, "str"),  # type: ignore[reportUnknownArgumentType]
                    required=bool(field_required_raw),  # type: ignore[reportUnknownArgumentType]
                    description=str(field_desc_raw),  # type: ignore[reportUnknownArgumentType]
                )
            )
        else:
            # Simple key: value → field with default type
            fields.append(TemplateField(name=key))

    return Template(
        meta=meta,
        fields=fields,
        body=parsed.content,
        raw=raw,
    )
