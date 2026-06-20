"""Chat dependency injection factories.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import (
    SessionDep,
    get_composer,
    get_invocation_pipeline,
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
    - InvocationPipeline for enrichment, budget, and evidence (ADR-048
      Mode 2 — agent-internal composition via ChatAgent).
    - DefaultRunLimitResolver for output-budget enforcement (ADR-045
      Decision 4).

    Args:
        session: SQLAlchemy async session for DB access.

    Returns:
        Configured ChatService ready for use.
    """
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(category=SystemModelCategory.ANALYSIS)
    store = SQLAlchemyConversationStore(session)
    invocation_pipeline = get_invocation_pipeline()
    run_limit_resolver = DefaultRunLimitResolver()

    return ChatService(
        prompt_composer=composer,
        model_registry=registry,
        conversation_store=store,
        config=config,
        invocation_pipeline=invocation_pipeline,
        run_limit_resolver=run_limit_resolver,
    )
