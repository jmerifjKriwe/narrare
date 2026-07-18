"""Consistency-feedback mem0 singleton factory (CR-AUFG-03-10).

Mirrors :func:`narrare.writing.deps_writing._get_session_memory_instance`
exactly — a module-level singleton that returns a long-lived
:class:`ConsistencyFeedbackService` (wrapping a mem0 client) or ``None``
when mem0 is unavailable. Lives in its own module so both
:mod:`narrare.kb._dismissed_deps` (store hook) and
:mod:`narrare.kb._consistency_deps` (retrieve+suppress hook) can import it
without creating a circular dependency (RULE-04).

Graceful degradation (RULE-11): returns ``None`` when mem0 is not
installed, no provider credentials exist, or client creation fails. Any
exception during initialization is caught so neither the dismiss nor the
consistency-check flow ever crashes due to the learning layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.memory.protocols import ConsistencyFeedbackCollector

logger = structlog.get_logger(__name__)

# Module-level singleton state — mutable, no @lru_cache (mirrors the
# session_memory pattern in writing/deps_writing.py).
_consistency_feedback_instance: ConsistencyFeedbackCollector | None = None
_consistency_feedback_init_tried: bool = False


def get_consistency_feedback_memory_instance() -> ConsistencyFeedbackCollector | None:
    """Create a ConsistencyFeedbackService if mem0 + credentials are available.

    Module-level singleton (mutable state, no ``@lru_cache``). Uses
    synchronous client creation for DI compatibility. The service holds a
    long-lived mem0 client that accepts per-call user/project IDs — safe for
    shared use across requests.

    Mirrors :func:`narrare.writing.deps_writing._get_session_memory_instance`
    exactly (graceful-degradation structure). Exposed as a public name
    because — unlike the writing singleton, which is called only within its
    own module — this one is consumed by both ``_dismissed_deps`` and
    ``_consistency_deps`` (same package, sibling modules).

    Graceful degradation (RULE-11): returns ``None`` when mem0 is not
    installed, no provider credentials exist, or client creation fails.
    Any exception during initialization is caught so the dismiss and
    consistency-check services never crash due to a memory subsystem issue.
    """
    global _consistency_feedback_instance, _consistency_feedback_init_tried

    if _consistency_feedback_init_tried:
        return _consistency_feedback_instance

    _consistency_feedback_init_tried = True

    try:
        from narrare._app.config import get_settings
        from narrare_core.memory._null_client import NullMemoryClient
        from narrare_core.memory.availability import (
            detect_provider_from_env,
            is_mem0_available,
        )
        from narrare_core.memory.consistency_feedback_service import (
            ConsistencyFeedbackService,
        )
        from narrare_core.memory.mem0_client import create_memory_client_sync

        # 1. Check mem0 is installed (encapsulated in core adapter)
        if not is_mem0_available():
            logger.info("consistency_feedback_disabled_mem0_not_installed")
            return None

        # 2. Detect provider from env (public API from core adapter)
        provider_config = detect_provider_from_env()
        if provider_config is None:
            logger.info("consistency_feedback_disabled_no_credentials")
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
                "consistency_feedback_client_creation_failed",
                provider=provider_config.provider,
            )
            return None

        _consistency_feedback_instance = ConsistencyFeedbackService(mem0_client=client)
        logger.info(
            "consistency_feedback_initialized",
            provider=provider_config.provider,
        )
        return _consistency_feedback_instance
    except Exception:
        logger.warning("consistency_feedback_init_failed", exc_info=True)
        return None
