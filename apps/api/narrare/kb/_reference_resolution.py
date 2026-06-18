"""KB reference resolution implementation (extracted for RULE-04).

Pure text→reference resolution: scans text for ``@Name`` mentions and
resolves them against KB entries. Extracted from ``service.py`` so the
service module stays within its RULE-04 line budget; the service exposes
``resolve_references`` as a thin delegator (public API unchanged).

Uses ``MENTION_RE`` and ``generate_reference_html`` from ``_utils``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.kb._utils import MENTION_RE, generate_reference_html
from narrare.kb.schemas import (
    ReferenceResolution,
    ResolveReferencesResponse,
)

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol


async def resolve_references(
    repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
    text: str,
) -> ResolveReferencesResponse:
    """Resolve every ``@Name`` mention in ``text`` to a KB entry.

    Mentions matching an entry name (case-insensitive) are linked;
    unmatched mentions are returned without an ``entry_id``. All mentions
    are optional — missing entries never cause errors.

    Args:
        repo: KB repository for name lookups.
        novel_id: Novel to scope lookups to.
        text: Source text to scan for mentions.

    Returns:
        Resolution response with linked references and rendered HTML.
    """
    mentions = {m.group(1).strip() for m in MENTION_RE.finditer(text)}
    resolved: list[ReferenceResolution] = []

    for mention in mentions:
        entry = await repo.get_by_name(novel_id, mention)
        if entry is not None:
            resolved.append(
                ReferenceResolution(
                    mention=mention,
                    entry_id=str(entry.id),
                    entry_name=entry.name,
                    entity_type=entry.entity_type,
                    slug=entry.slug,
                )
            )
        else:
            resolved.append(ReferenceResolution(mention=mention))

    html = generate_reference_html(text, resolved, novel_id)
    return ResolveReferencesResponse(resolved=resolved, html=html)
