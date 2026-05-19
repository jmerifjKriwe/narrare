"""Schema bridge — connects template fields to KB metadata schemas.

Provides helpers that:
1. Load the default template for an entity type and extract form fields.
2. Validate a metadata dict against the appropriate KB schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from narrare_core.kb.schemas import KBEntryMetadata, get_schema

from .defaults import load_default_template
from .parser import parse_template

if TYPE_CHECKING:
    from .models import TemplateField


def get_form_fields(entity_type: str) -> list[TemplateField]:
    """Load template fields for an entity type, enriched with schema info.

    Loads the default English template for the entity type, parses it,
    and returns the field definitions.  If no template exists, returns
    an empty list.

    Args:
        entity_type: Entity type string (e.g. "character").

    Returns:
        List of TemplateField from the default template.
    """
    raw = load_default_template(entity_type, language="en")
    if raw is None:
        return []
    template = parse_template(raw)
    return template.fields


def validate_metadata(
    entity_type: str,
    metadata: dict[str, Any],
) -> KBEntryMetadata:
    """Validate a metadata dict against the schema for the entity type.

    Uses the schema registry to find the correct Pydantic model.
    Unknown entity types fall back to ``KBEntryMetadata`` (extra="allow").

    Args:
        entity_type: Entity type string (e.g. "character").
        metadata: Raw metadata dictionary to validate.

    Returns:
        Typed metadata model instance.

    Raises:
        pydantic.ValidationError: If metadata doesn't match the schema.
    """
    schema_cls = get_schema(entity_type)
    return schema_cls.model_validate(metadata)
