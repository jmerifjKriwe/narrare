"""KB deduplication context for name generation.

Pure helpers that feed existing KB entity names into the LLM prompt for
proactive dedup and flag generated names that match existing entries.
Handles the entity-type mapping (``NameType`` → KB ``entity_type``), the
governed page size (CR-AUFG-08-13), and the token budget applied to the
joined existing-names context.

This module has one responsibility (RULE-06): KB dedup context. Prompt
building, orchestration, and registry invocation stay in
:mod:`narrare.generation.name_service` (see
:mod:`narrare.generation.name_parsing` for the response-parsing sibling).

See:
    CONSTRAINTS.md RULE-06/RULE-11; Governed Defaults Manifest §4.2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.writing.budget import cap_to_budget

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.generation.schemas import GeneratedName
    from narrare.kb.contracts import KBRepositoryProtocol

logger = structlog.get_logger(__name__)

# Maximum token budget for existing-name dedup context sent to the LLM.
# At ~1.3 tokens/word this allows roughly 350 short entity names.
MAX_EXISTING_NAMES_TOKENS: int = 500

# Page size used when listing KB entries for name-dedup context — CR-AUFG-08-13.
# Single definition site (RULE-06): the name-service seam imports this rather
# than hardcoding the literal, so there is one place to review when the
# default changes. See the Governed Defaults Manifest §4.2 for rationale and
# review triggers.
DEFAULT_NAME_DEDUP_PAGE_SIZE: int = 1000

# Mapping from NameType enum values to KB entity_type values.
# NameType uses "place"/"organization"/"item" while the KB CHECK constraint
# uses "location"/"faction"/"object".
_NAME_TYPE_TO_KB_ENTITY: dict[str, str] = {
    "character": "character",
    "place": "location",
    "organization": "faction",
    "item": "object",
}


async def fetch_existing_names(
    kb_repo: KBRepositoryProtocol | None,
    project_id: UUID,
    name_type: str,
    *,
    page_size: int,
) -> list[str]:
    """Fetch existing entity names from the project's KB.

    Queries the KB repository filtered by the mapped entity type.
    Returns an empty list when no KB repository is configured.

    Args:
        kb_repo: The KB repository (or ``None`` for no dedup context).
        project_id: The project (novel) ID to query names for.
        name_type: The NameType value (e.g. "character", "place").
        page_size: Governed page size wired in by the service seam
            (``DEFAULT_NAME_DEDUP_PAGE_SIZE`` — single definition site).

    Returns:
        List of entity names from the KB, capped to the token budget.
    """
    if kb_repo is None:
        return []

    entity_type = _NAME_TYPE_TO_KB_ENTITY.get(name_type)
    entries, total = await kb_repo.list_entries(
        novel_id=project_id,
        entity_type=entity_type,
        page_size=page_size,
    )

    if total > len(entries):
        logger.warning(
            "kb_names_truncated",
            total=total,
            returned=len(entries),
            hint="Consider pagination if this occurs frequently",
        )

    names = [entry.name for entry in entries]

    # Enforce token budget — truncate the list when the joined
    # string exceeds the allowed budget so prompts never overflow.
    joined = ", ".join(names)
    capped = cap_to_budget(joined, MAX_EXISTING_NAMES_TOKENS)
    result = [n.strip() for n in capped.split(",") if n.strip()]

    if len(result) < len(names):
        logger.info(
            "existing_names_capped",
            original=len(names),
            capped=len(result),
            budget=MAX_EXISTING_NAMES_TOKENS,
        )

    return result


def flag_duplicates(
    names: list[GeneratedName],
    existing_names: list[str],
) -> list[GeneratedName]:
    """Flag generated names that match existing KB entries.

    Compares case-insensitively with trimmed whitespace.
    Does NOT remove duplicates — only sets is_duplicate=True.

    Args:
        names: Generated names to check.
        existing_names: KB entity names to compare against.

    Returns:
        The same list with is_duplicate flags set where applicable.
    """
    existing_lower = {n.strip().lower() for n in existing_names}
    for name_obj in names:
        if name_obj.name.strip().lower() in existing_lower:
            name_obj.is_duplicate = True
    return names
