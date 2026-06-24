"""CR-AUFG-07-19 — pure mapping helpers for ``PromptHistoryApiService``.

Extracted from ``history_service.py`` per RULE-04 (file-size limit).  These
helpers are pure (no I/O): content hashing, revision → response mapping, and
the ``"active"`` compare token.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from narrare.prompts.schemas_prompt_history import (
    PromptHistoryScope,
    PromptRevisionResponse,
)

if TYPE_CHECKING:
    from narrare.prompts.models import PromptRevision

#: Literal token accepted by compare endpoints to mean "the current active
#: override file" rather than a revision UUID.
ACTIVE_TOKEN = "active"  # nosec B105  # sentinel marker: "current active override", not a credential


def content_hash(text: str) -> str:
    """Return the sha256 hex digest of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode()).hexdigest()


def revision_to_response(
    revision: PromptRevision,
    *,
    active_hash: str | None,
) -> PromptRevisionResponse:
    """Map an ORM revision row to the wire schema with derived ``is_active``.

    Args:
        revision: A ``PromptRevision`` ORM row.
        active_hash: sha256 of the current active override file, or ``None``
            when no override is set.  ``is_active`` is ``True`` only when the
            revision's stored hash equals ``active_hash``.

    Returns:
        A ``PromptRevisionResponse`` ready for the API boundary.
    """
    return PromptRevisionResponse(
        id=revision.id,
        prompt_id=revision.prompt_id,
        scope=PromptHistoryScope(revision.scope),
        content=revision.content,
        content_hash=revision.content_hash,
        actor_id=revision.actor_id,
        source=revision.source,
        change_reason=revision.change_reason,
        restored_from_id=revision.restored_from_id,
        created_at=revision.created_at,
        is_active=(active_hash is not None and revision.content_hash == active_hash),
    )
