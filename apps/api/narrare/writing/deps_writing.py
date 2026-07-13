"""Writing module dependency injection — writing service factory."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.kb.relationship_repository import RelationshipRepository
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import SUGGEST_MAX_TOKENS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.service import WritingService
    from narrare_core.memory.session_memory_service import SessionMemoryService

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SessionMemoryService singleton (mirrors preference_service pattern in
# _app/dependencies_prompts.py — long-lived mem0 client, safe for shared use)
# ---------------------------------------------------------------------------

_session_memory_instance: SessionMemoryService | None = None
_session_memory_init_tried: bool = False


def _get_session_memory_instance() -> SessionMemoryService | None:
    """Create a SessionMemoryService if mem0 + credentials available, else None.

    Module-level singleton (mutable state, no ``@lru_cache``).  Uses
    synchronous client creation for DI compatibility.  The
    SessionMemoryService holds a long-lived mem0 client that accepts
    per-call user/project IDs — safe for shared use.

    Graceful degradation (RULE-11): returns ``None`` when mem0 is not
    installed, no provider credentials exist, or client creation fails.
    Any exception during initialization is caught so the writing service
    never crashes due to a memory subsystem issue.
    """
    global _session_memory_instance, _session_memory_init_tried

    if _session_memory_init_tried:
        return _session_memory_instance

    _session_memory_init_tried = True

    try:
        from narrare._app.config import get_settings
        from narrare_core.memory._null_client import NullMemoryClient
        from narrare_core.memory.availability import (
            detect_provider_from_env,
            is_mem0_available,
        )
        from narrare_core.memory.mem0_client import create_memory_client_sync
        from narrare_core.memory.session_memory_service import SessionMemoryService

        # 1. Check mem0 is installed (encapsulated in core adapter)
        if not is_mem0_available():
            logger.info("session_memory_disabled_mem0_not_installed")
            return None

        # 2. Detect provider from env (public API from core adapter)
        provider_config = detect_provider_from_env()
        if provider_config is None:
            logger.info("session_memory_disabled_no_credentials")
            return None

        # 3. Create mem0 client synchronously
        settings = get_settings()
        client = create_memory_client_sync(
            provider=provider_config.provider,
            api_key=provider_config.api_key,
            base_url=provider_config.base_url,
            memory_model=settings.memory_llm_model,
            embedding_model=settings.memory_embedding_model,
        )

        if isinstance(client, NullMemoryClient):
            logger.warning(
                "session_memory_client_creation_failed",
                provider=provider_config.provider,
            )
            return None

        _session_memory_instance = SessionMemoryService(mem0_client=client)
        logger.info(
            "session_memory_initialized",
            provider=provider_config.provider,
        )
        return _session_memory_instance
    except Exception:
        logger.warning("session_memory_init_failed", exc_info=True)
        return None


async def get_writing_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
    intent: LLMIntent = LLMIntent.WRITE,
) -> WritingService:
    """Factory for WritingService — resolves model config per user/intent.

    Args:
        session: DB session for repository and settings lookups.
        user_id: Authenticated user identifier.
        project_id: Optional project/novel ID for project-level settings.
        intent: LLM operation intent.  Controls model routing and prompt
            selection.  Defaults to ``LLMIntent.WRITE`` (full chapter).
            Use ``LLMIntent.SUGGEST`` for lightweight inline suggestions.

    Returns:
        Configured WritingService ready for use.
    """
    from narrare._app.config import get_settings
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.repository import UserSettingsRepository
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing.deps_pipeline import create_pipeline
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.service import WritingService
    from narrare_core.writing.draft_processor import DraftProcessor

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        intent,
        UUID(user_id),
        project_id,
    )
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(project_id) if project_id else None,
    )
    config = replace(
        resolved.config,
        temperature=0.7,
        max_tokens=limits.output_limit,
    )
    if intent == LLMIntent.SUGGEST:
        # SUGGEST uses a fixed 60-token limit — inline suggestions must be short
        # (UX constraint, not a profile concern).
        config = replace(config, temperature=0.3, max_tokens=SUGGEST_MAX_TOKENS)

    draft_processor = DraftProcessor()
    pipeline = create_pipeline(draft_processor, tier_overrides=limits.tier_percentages)
    repo = GenerationRepository(session)
    relationship_repo = RelationshipRepository(session)
    tone_service = CustomToneService(repo=UserSettingsRepository(session))
    session_memory = _get_session_memory_instance()

    return WritingService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        tone_service=tone_service,
        relationship_repo=relationship_repo,
        session_memory=session_memory,
    )
