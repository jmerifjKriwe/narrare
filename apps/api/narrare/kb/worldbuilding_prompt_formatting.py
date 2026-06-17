"""Phase 2 prompt-variable formatting helpers.

Renders WorldbuildingDeps data into the readable strings that the phase2
prompt template substitutes for ``{{candidate_pairs}}``,
``{{entity_details}}``, and ``{{existing_relationships}}``.

Extracted from :mod:`narrare.kb.worldbuilding_analyzer` for RULE-04.
Formatting lives at the analyzer layer because the data is composed from
per-phase deps (ADR-048 Mode 2); the governed variable engine handles the
actual substitution.
"""

from __future__ import annotations

from typing import cast


def _entity_label(eid: str, entity_details: dict[str, dict[str, object]]) -> str:
    """Format a human-readable label for an entity ID.

    Args:
        eid: Entity identifier.
        entity_details: Resolved entity details (for human-readable names).

    Returns:
        ``"Name (id)"`` when details are known, otherwise the raw id.
    """
    details = entity_details.get(eid)
    if details:
        name = str(details.get("name") or eid)
        return f"{name} ({eid})"
    return eid


def format_candidate_pairs(
    pairs: list[tuple[str, str]],
    entity_details: dict[str, dict[str, object]],
) -> str:
    """Render candidate entity pairs for the phase2 prompt.

    Args:
        pairs: Entity ID tuples to check for consistency.
        entity_details: Resolved entity details (for human-readable names).

    Returns:
        Newline-separated list of "NameA (id) ↔ NameB (id)" entries, or
        empty string when no pairs were selected.
    """
    if not pairs:
        return ""
    lines: list[str] = []
    for src_id, tgt_id in pairs:
        lines.append(
            f"- {_entity_label(src_id, entity_details)} ↔ {_entity_label(tgt_id, entity_details)}"
        )
    return "\n".join(lines)


def format_entity_details(entity_details: dict[str, dict[str, object]]) -> str:
    """Render entity details for the phase2 prompt.

    Args:
        entity_details: Full entity details keyed by entity ID.

    Returns:
        Newline-separated entity blocks (name, type, body, tags), or empty
        string when no entity details were loaded.
    """
    if not entity_details:
        return ""
    blocks: list[str] = []
    for eid, details in entity_details.items():
        name = details.get("name") or eid
        etype = details.get("entity_type") or "unknown"
        body = details.get("body") or ""
        raw_tags = details.get("tags")
        if isinstance(raw_tags, list):
            tags_str = ", ".join(map(str, cast("list[object]", raw_tags)))
        elif raw_tags:
            tags_str = str(raw_tags)
        else:
            tags_str = ""
        lines = [f"### {name} ({etype}) [id: {eid}]"]
        if body:
            lines.append(f"Body: {body}")
        if tags_str:
            lines.append(f"Tags: {tags_str}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_relationships(relationships: list[dict[str, object]]) -> str:
    """Render existing relationships for the phase2 prompt.

    Args:
        relationships: Relationship dicts (source_id, target_id, rel_type,
            direction) as assembled by worldbuilding_entity_assembly.

    Returns:
        Newline-separated "source --[rel]--> target" entries, or empty
        string when there are no relationships.
    """
    if not relationships:
        return ""
    lines: list[str] = []
    for rel in relationships:
        source = rel.get("source_id") or "?"
        target = rel.get("target_id") or "?"
        rel_type = rel.get("rel_type") or "related"
        direction = rel.get("direction") or ""
        arrow = "<-->" if direction == "bidirectional" else "-->"
        lines.append(f"- {source} {arrow}[{rel_type}] {target}")
    return "\n".join(lines)
