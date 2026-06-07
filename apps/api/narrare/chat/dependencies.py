"""Chat dependency injection factories.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import (
    SessionDep,
    get_composer,
    get_model_registry,
)

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService


def get_chat_service(session: SessionDep) -> ChatService:
    """Create a ChatService with injected dependencies.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - SQLAlchemyConversationStore for message persistence
    - System-default model config for the chat intent

    Args:
        session: SQLAlchemy async session for DB access.

    Returns:
        Configured ChatService ready for use.
    """
    from narrare._app.dependencies_services import build_system_default_config
    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(category="analysis")
    store = SQLAlchemyConversationStore(session)

    return ChatService(
        prompt_composer=composer,
        model_registry=registry,
        conversation_store=store,
        config=config,
    )
