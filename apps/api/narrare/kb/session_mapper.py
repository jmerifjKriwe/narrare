"""Maps KB creation sessions to KBEntryCreate for persistence.

Strategy:
- session.name → entry.name (required, raises ValueError if None)
- session.entity_type → entry.entity_type
- Structured metadata fields (flat) → entry.metadata dict
- Dot-notation fields (appearance.height) → nested metadata dict via unflatten
- All filled fields → entry.body (structured markdown)
- entry.status = "draft"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare.kb.schemas import KBEntryCreate

if TYPE_CHECKING:
    from narrare.kb.session_models import KBCreationSession


def map_session_to_entry(session: KBCreationSession) -> KBEntryCreate:
    """Map session fields to KBEntryCreate.

    Args:
        session: The completed session with filled fields.

    Returns:
        KBEntryCreate ready for persistence via KBService.create.

    Raises:
        ValueError: If session.name is None.
    """
    if not session.name:
        raise ValueError("Session must have a name before completion")

    # Collect filled fields (skip empty ones)
    filled: dict[str, str] = {}
    for field in session.fields:
        val = field.final_value or field.user_value or field.ai_suggested_value
        if val:
            filled[field.field_key] = val

    # Build metadata from filled fields (unflatten dot-notation)
    metadata = _unflatten_fields(filled)

    # Build body as structured markdown
    body = _build_body(session.name, session.entity_type, filled)

    return KBEntryCreate(
        entity_type=session.entity_type,
        name=session.name,
        status="draft",
        metadata=metadata if metadata else None,
        body=body,
    )


def _unflatten_fields(flat: dict[str, str]) -> dict[str, object]:
    """Convert {'appearance.height': '180cm'} → {'appearance': {'height': '180cm'}}.

    Fields without dots remain at the top level.
    """
    result: dict[str, object] = {}
    for key, value in flat.items():
        parts = key.split(".")
        if len(parts) == 1:
            result[key] = value
        else:
            current: dict[str, object] = result
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                nested = current[part]
                if not isinstance(nested, dict):
                    nested = {}
                    current[part] = nested
                current = cast("dict[str, object]", nested)
            current[parts[-1]] = value
    return result


def _build_body(name: str, entity_type: str, fields: dict[str, str]) -> str:
    """Build structured markdown body from session fields.

    Produces:
        # {name}

        **Type:** {entity_type}

        **{Label}:** {value}

        ...
    """
    lines = [f"# {name}", "", f"**Type:** {entity_type}", ""]
    for key, value in fields.items():
        label = key.replace("_", " ").replace(".", " > ").title()
        lines.append(f"**{label}:** {value}")
        lines.append("")
    return "\n".join(lines).strip()
