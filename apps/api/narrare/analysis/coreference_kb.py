"""KB character context for coreference resolution (RULE-04 split).

Extracted from ``coreference_service.py`` to keep that file under the
300-line hard limit (RULE-04). Builds the ``kb_characters`` prompt
variable — the character name list that coreference resolution needs to
map pronouns → characters.

The fetch+format lives here; the graceful-degradation policy (catching
errors and falling back to an empty string) is owned by the caller
(:class:`~narrare.analysis.coreference_service.CoreferenceService`),
per RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.repository import KBRepository


async def fetch_kb_characters(kb_repo: KBRepository, novel_id: UUID) -> str:
    """Fetch KB character entries and format them for the coreference prompt.

    Loads all entries for the novel (capped at 200 to bound the prompt),
    filters to ``character`` entity types, and renders each as
    ``- {name}: {body}`` with the body truncated to 200 characters.

    Args:
        kb_repo: The KB repository to query.
        novel_id: The novel whose characters to load.

    Returns:
        A newline-joined list of character summaries, or an empty string
        when the novel has no character entries.

    Raises:
        Exception: Propagates repository errors to the caller, which is
            responsible for graceful degradation (RULE-11: log a warning
            and continue with an empty string).
    """
    entries, _ = await kb_repo.list_entries(novel_id, page_size=200)
    characters = [e for e in entries if e.entity_type == "character"]
    return "\n".join(f"- {e.name}: {(e.body or '')[:200]}" for e in characters if e.name)
