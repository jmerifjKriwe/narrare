"""Chat service — Free-Form Chat for Writing Craft.

This package provides contracts and core logic for the free-form chat feature
(ADR-024, CR-AUFG-02-03). The chat module enables authors to ask open-ended
questions about their project and writing craft — distinct from the production-
oriented interactive session mode.

Domain: core/chat/ — no HTTP, no DB, no FastAPI imports.
"""

from narrare_core.chat.contracts import (
    ChatConversation,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatServiceProtocol,
)

__all__ = [
    "ChatConversation",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatServiceProtocol",
]
