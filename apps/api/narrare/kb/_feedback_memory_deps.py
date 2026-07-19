"""Consistency-feedback mem0 singleton factory (CR-AUFG-03-10).

Mirrors :func:`narrare.writing._session_memory_deps.get_session_memory_instance`
structurally — a module-level singleton that returns a long-lived
:class:`ConsistencyFeedbackService` (wrapping a mem0 client) or ``None``
when mem0 is unavailable. Lives in its own module so both
:mod:`narrare.kb._dismissed_deps` (store hook) and
:mod:`narrare.kb._consistency_deps` (retrieve+suppress hook) can import it
without creating a circular dependency (RULE-04).

Graceful degradation (RULE-11): returns ``None`` when mem0 is not
installed, no provider credentials exist, or client creation fails. Any
exception during initialization is caught so neither the dismiss nor the
consistency-check flow ever crashes due to the learning layer.

The ``is_mem0_available`` and ``detect_provider_from_env`` imports live at
MODULE LEVEL (not inside the function) so the autouse ``_no_real_mem0_clients``
test guard in ``tests/conftest.py`` can patch the re-imported reference —
matching the pattern in :mod:`narrare._app.dependencies_prompts`. This
prevents the singleton from creating a real ``mem0.AsyncMemory`` client
(Qdrant + sqlite resources) in the test environment, which would otherwise
leak across event loops under pytest-asyncio and surface as
``RuntimeError: Task got Future attached to a different loop`` at teardown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.memory.availability import (
    detect_provider_from_env,
    is_mem0_available,
)

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

    Mirrors :func:`narrare.writing._session_memory_deps.get_session_memory_instance`
    exactly (graceful-degradation structure). Exposed as a public name
    because it is consumed by both ``_dismissed_deps`` and
    ``_consistency_deps`` (same package, sibling modules) — the same
    cross-module convention the writing singleton follows after its
    RULE-04 extraction into ``_session_memory_deps.py``.

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
        from narrare_core.memory.consistency_feedback_service import (
            ConsistencyFeedbackService,
        )
        from narrare_core.memory.mem0_client import create_memory_client_sync

        # 1. Check mem0 is installed (encapsulated in core adapter).
        # ``is_mem0_available`` is imported at module level so the autouse
        # ``_no_real_mem0_clients`` test guard can patch this module's
        # reference (matches the dependencies_prompts.py pattern).
        if not is_mem0_available():
            logger.info("consistency_feedback_disabled_mem0_not_installed")
            return None

        # 2. Detect provider from env (public API from core adapter).
        # Same module-level import rationale as is_mem0_available above.
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
