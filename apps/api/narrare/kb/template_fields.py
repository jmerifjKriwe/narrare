"""Template field extraction from KB schema registry.

Maps Pydantic model fields to KBCreationField objects for the
assisted creation session UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from narrare_core.kb.schemas.registry import get_schema

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

from .session_models import KBCreationField

# Type alias for the field_type literal
FieldType = Literal["text", "list", "boolean", "select"]


def get_template_fields(entity_type: str) -> list[KBCreationField]:
    """Extract creation fields from KB schema for the given entity type.

    Uses the schema registry to determine which fields are available
    for the entity type. Nested field groups are flattened with
    dot notation (e.g. "appearance.height").

    Args:
        entity_type: Entity type string (e.g. "character", "location").

    Returns:
        List of KBCreationField objects describing the template.
    """
    schema_cls = get_schema(entity_type)
    fields: list[KBCreationField] = []

    for field_name, field_info in schema_cls.model_fields.items():
        field_type_val = _map_field_type(field_info)
        label = field_name.replace("_", " ").title()
        required = field_info.is_required()

        # Check for nested model fields (e.g. AppearanceFields)
        annotation = field_info.annotation
        if _is_nested_model(annotation):
            nested_fields = _extract_nested_fields(field_name, annotation)
            fields.extend(nested_fields)
        else:
            fields.append(
                KBCreationField(
                    field_key=field_name,
                    label=label,
                    field_type=field_type_val,
                    required=required,
                )
            )

    return fields


def _is_nested_model(annotation: object | None) -> bool:
    """Check if an annotation is a nested Pydantic model (not a primitive)."""
    if annotation is None:
        return False

    # Handle Optional[X] / X | None
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        # For Union types (X | None), check the non-None args
        args = getattr(annotation, "__args__", ())
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            inner = non_none_args[0]
            return _is_pydantic_model(inner)
        return False

    return _is_pydantic_model(annotation)


def _is_pydantic_model(annotation: object) -> bool:
    """Check if an annotation is a Pydantic BaseModel subclass."""
    try:
        return isinstance(annotation, type) and issubclass(annotation, BaseModel)
    except TypeError:
        return False


def _extract_nested_fields(
    parent_key: str,
    annotation: object,
) -> list[KBCreationField]:
    """Extract fields from a nested Pydantic model with dot notation.

    Args:
        parent_key: The parent field name (e.g. "appearance").
        annotation: The nested model class.

    Returns:
        List of KBCreationField objects with dot-notation keys.
    """
    # Handle Optional[X] / X | None
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            annotation = non_none_args[0]

    if not _is_pydantic_model(annotation):
        return []

    model_cls: type[BaseModel] = annotation  # type: ignore[assignment]
    fields: list[KBCreationField] = []
    for field_name, field_info in model_cls.model_fields.items():
        field_type_val = _map_field_type(field_info)
        dot_key = f"{parent_key}.{field_name}"
        label = f"{parent_key.title()} {field_name.replace('_', ' ').title()}"
        required = field_info.is_required()

        fields.append(
            KBCreationField(
                field_key=dot_key,
                label=label,
                field_type=field_type_val,
                required=required,
            )
        )

    return fields


def _map_field_type(field_info: FieldInfo) -> FieldType:
    """Map a Pydantic field annotation to a KBCreationField field type."""
    annotation = field_info.annotation
    if annotation is None:
        return "text"

    # Handle Optional[X] / X | None — unwrap to inner type
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            annotation = non_none_args[0]

    # list[str] → "list"
    list_origin = (
        getattr(annotation, "__origin__", None) if hasattr(annotation, "__origin__") else None
    )
    if list_origin is list:
        return "list"

    # bool → "boolean"
    if annotation is bool:
        return "boolean"

    # Default: text
    return "text"
