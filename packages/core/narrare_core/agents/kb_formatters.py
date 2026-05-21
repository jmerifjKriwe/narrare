"""KB-Format-Helper — Formatierungslogik für KBAgent-Tools.

Eigene Datei wegen RULE-04 (File-Size-Limit).
Enthält nur reine Formatierungsfunktionen, kein I/O, keine Agent-Logik.
"""

from __future__ import annotations

from typing import Any


def format_entries(entries: list[Any]) -> str:
    """Format a list of KB entries as a readable string.

    Args:
        entries: List of KB entry objects.

    Returns:
        Formatted string with up to 10 entries.
    """
    lines = ["Found KB entries:"]
    for e in entries[:10]:  # Limit to 10
        name = getattr(e, "name", str(e))
        etype = getattr(e, "entity_type", "unknown")
        body = getattr(e, "body", getattr(e, "description", ""))
        preview = body[:200] if body else "(no content)"
        lines.append(f"  \u2022 {name} [{etype}]: {preview}")
    if len(entries) > 10:
        lines.append(f"  ... and {len(entries) - 10} more entries")
    return "\n".join(lines)


def format_entity(entity: Any) -> str:
    """Format a single KB entity as a readable string.

    Args:
        entity: A KB entry object.

    Returns:
        Formatted entity details.
    """
    name = getattr(entity, "name", str(entity))
    etype = getattr(entity, "entity_type", "unknown")
    body = getattr(entity, "body", getattr(entity, "description", ""))
    tags = getattr(entity, "tags", [])
    status = getattr(entity, "status", "draft")

    lines = [
        f"Entity: {name}",
        f"Type: {etype}",
        f"Status: {status}",
    ]
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")
    if body:
        lines.append(f"\nContent:\n{body[:500]}")
    return "\n".join(lines)


def format_related(entity_name: str, relations: list[Any]) -> str:
    """Format related entities as a readable string.

    Args:
        entity_name: Name of the source entity.
        relations: List of relationship objects.

    Returns:
        Formatted list of related entities (up to 15).
    """
    lines = [f"Entities related to '{entity_name}':"]
    for r in relations[:15]:
        target = getattr(r, "target_name", str(r))
        rel_type = getattr(r, "rel_type", "related")
        lines.append(f"  \u2022 {target} ({rel_type})")
    return "\n".join(lines)
