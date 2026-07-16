"""Curated world-context builder for KB operations (RULE-04 helper).

Builds the ``{{world_context}}`` prompt variable from existing KB entries.
This is the genuine runtime source for the ``<curated_kb_context>`` slot in
the kb/merge and kb/extract governed templates — the same data that the kb
assist/improve services surface as ``deps.world_context`` and that the
worldbuilding analyser loads via ``worldbuilding_entity_assembly``.

The helper deliberately mirrors two established precedents:
- KB-entity fetching (``list_entities`` / ``kb_repo.list_entries``).
- Graceful degradation (RULE-11): a repository failure or an empty KB yields
  an empty string so the caller (merge/extract) proceeds without crashing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry

logger = structlog.get_logger(__name__)

#: Metadata keys inspected (in order) when looking for a one-line description.
_BRIEF_METADATA_KEYS = ("description", "role", "summary", "function")


def format_world_context(
    entries: list[KBEntry],
    *,
    max_entries: int = 30,
) -> str:
    """Format KB entries as a curated world-context string.

    Renders a compact, structured list (entity keyword + bullet structure)
    that satisfies ``validate_world_context`` heuristics. Each rendered line
    has the shape ``- {name} ({entity_type}): {brief}`` where ``{brief}`` is
    a short metadata/body excerpt (omitted when unavailable). Entries without
    a usable name are skipped.

    Field access is best-effort (``getattr``): world_context is enrichment,
    so a partial entry degrades to its name rather than crashing the caller.

    Args:
        entries: KB entries to render.
        max_entries: Upper bound on the number of entries rendered.

    Returns:
        The formatted context, or an empty string when ``entries`` is empty.
    """
    if not entries:
        return ""

    lines: list[str] = []
    for entry in entries[:max_entries]:
        name = getattr(entry, "name", None)
        if not name:
            continue
        entity_type = getattr(entry, "entity_type", "") or ""
        brief = _brief_description(entry)
        type_part = f" ({entity_type})" if entity_type else ""
        suffix = f": {brief}" if brief else ""
        lines.append(f"- {name}{type_part}{suffix}")
    return "\n".join(lines)


def _brief_description(entry: KBEntry, *, max_brief_chars: int = 240) -> str:
    """Extract a short description from metadata, falling back to the body."""
    raw_metadata = getattr(entry, "metadata_", None)
    metadata = dict(raw_metadata or {})
    for key in _BRIEF_METADATA_KEYS:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:max_brief_chars]

    body = (getattr(entry, "body", None) or "").strip()
    return body[:max_brief_chars] if body else ""


async def fetch_world_context(
    kb_repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
    *,
    entity_type: str | None = None,
    max_entries: int = 30,
) -> str:
    """Fetch existing KB entries and format them as curated world context.

    Graceful degradation (RULE-11): when the repository is unavailable or
    returns no entries, logs a warning and returns an empty string so the
    caller (merge/extract) proceeds without crashing. Avoidance/preference
    data is intentionally not handled here — it reaches the prompt via the
    ``user_preferences`` variable (see ``enrichers.preferences``).

    Args:
        kb_repo: KB entry repository (scoped read).
        novel_id: Novel whose KB entries provide the curated context.
        entity_type: Optional entity-type filter (e.g. the type being merged).
        max_entries: Upper bound on entries rendered.

    Returns:
        The formatted world context, or ``""`` on failure / empty KB.
    """
    try:
        entries, _ = await kb_repo.list_entries(
            novel_id=novel_id,
            entity_type=entity_type,
            page=1,
            page_size=max_entries,
        )
    except Exception:
        logger.warning("world_context_fetch_unavailable", exc_info=True)
        return ""
    return format_world_context(list(entries), max_entries=max_entries)
