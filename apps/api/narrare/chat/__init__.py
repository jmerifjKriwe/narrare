"""Chat service — Free-Form Chat for Writing Craft (ADR-024).

Backend implementation of the free-form chat feature.
Wires core chat logic (narrare_core.chat) to FastAPI infrastructure.

Domain: apps/api/narrare/chat/ — FastAPI routes, SQLAlchemy persistence.
"""

from narrare.chat.chat_service import ChatService
from narrare.chat.conversation_store import SQLAlchemyConversationStore

__all__ = [
    "ChatService",
    "SQLAlchemyConversationStore",
]
