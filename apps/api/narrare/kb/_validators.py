"""KB entry validation helpers — metadata and slug validation."""

from __future__ import annotations

from narrare.kb._utils import slugify
from narrare_core.shared.errors import ValidationError
from narrare_core.templates.schema_bridge import validate_metadata


def validate_entry_metadata(entity_type: str, metadata: dict[str, object]) -> None:
    """Validate metadata against core schema registry.

    Args:
        entity_type: The entity type to validate against.
        metadata: Metadata dict to validate.

    Raises:
        ValidationError: If metadata is invalid for the entity type.
    """
    try:
        validate_metadata(entity_type, metadata)
    except Exception as exc:
        raise ValidationError(f"Invalid metadata for entity type '{entity_type}': {exc}") from exc


def resolve_entry_slug(provided_slug: str | None, name: str) -> str:
    """Generate or validate slug for entry creation.

    Args:
        provided_slug: Explicit slug if provided, None to auto-generate.
        name: Entry name for auto-generation.

    Returns:
        Validated slug string.

    Raises:
        ValidationError: If no valid slug can be generated.
    """
    slug = provided_slug or slugify(name)
    if not slug:
        raise ValidationError("Could not generate a valid slug from the name")
    return slug
