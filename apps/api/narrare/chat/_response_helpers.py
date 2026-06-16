"""Helper for persisting chat assistant responses.

Extracted from ``chat_service.py`` for RULE-04 compliance.
One responsibility (RULE-06): persist assistant responses to the store.

See: ADR-045, ADR-048, CONSTRAINTS.md RULE-04/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chat.conversation_store import SQLAlchemyConversationStore


async def save_assistant_response(
    store: SQLAlchemyConversationStore,
    conv_id: UUID,
    response: str,
) -> None:
    """Persist assistant response if non-empty.

    Graceful degradation: skips persistence when ``response`` is empty
    (RULE-11 — no silent failure, just intentional no-op).

    Args:
        store: The conversation store for persistence.
        conv_id: The conversation UUID.
        response: The assistant response text to persist.
    """
    if response:
        await store.add_message(conv_id, "assistant", response)
