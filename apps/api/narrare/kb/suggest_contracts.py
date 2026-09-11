"""KB suggestion service contract — Protocol definition.

Extracted from contracts.py per RULE-04 (file size limit).
Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.kb.schemas import KBSuggestionResponse


@runtime_checkable
class KBSuggestProtocol(Protocol):
    """Protocol for KB suggestion API service.

    ``get_suggestions`` is gated on novel ownership (IDOR fix S9): the
    caller must own ``novel_id`` BEFORE chapter content or KB entries are
    loaded — foreign and unknown novels are indistinguishable
    (``NotFoundError`` → 404).
    """

    async def get_suggestions(
        self,
        chapter_id: uuid.UUID,
        *,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        max_results: int = 20,
    ) -> list[KBSuggestionResponse]: ...
