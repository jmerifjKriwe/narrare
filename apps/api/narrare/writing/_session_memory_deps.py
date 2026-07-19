"""Session-memory mem0 singleton factory (RULE-04 extraction).

Hosts the ``get_session_memory_instance`` singleton in its own module so
that:

1. ``deps_writing.py`` stays under the 200-line RULE-04 size limit after
   follow-up #1 moved the ``is_mem0_available`` /
   ``detect_provider_from_env`` imports to module level (required for the
   ``_no_real_mem0_clients`` test guard patch target).
2. The autouse ``_no_real_mem0_clients`` test guard can patch
   ``is_mem0_available`` at module level (per ADR-068 — see
   ``docs/architecture/decisions/ADR-068-mem0-test-isolation-guard-pattern.md``).

Mirrors :mod:`narrare.kb._feedback_memory_deps` structurally — a
module-level singleton returning a long-lived
:class:`SessionMemoryService` (wrapping a mem0 client) or ``None`` when
mem0 is unavailable. The function is exposed as a PUBLIC name (not
``_``-prefixed) because — like
:func:`narrare.kb._feedback_memory_deps.get_consistency_feedback_memory_instance`
— it is consumed by a sibling module (``deps_writing.py``), not only
within its own module.

The ``is_mem0_available`` and ``detect_provider_from_env`` imports live at
MODULE LEVEL (not inside the function body) so the autouse
``_no_real_mem0_clients`` test guard in ``tests/unit/conftest.py`` and
``tests/integration/conftest.py`` can patch the re-imported reference.
This prevents the singleton from creating a real ``mem0.AsyncMemory``
client (Qdrant + sqlite resources) in the test environment, which would
otherwise leak across event loops under pytest-asyncio and surface as
``RuntimeError: Task got Future attached to a different loop`` at
teardown. See ADR-068 (Decision 1) for the full rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.memory.availability import (
    detect_provider_from_env,
    is_mem0_available,
)

if TYPE_CHECKING:
    from narrare_core.memory.session_memory_service import SessionMemoryService

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SessionMemoryService singleton (mirrors preference_service pattern in
# _app/dependencies_prompts.py — long-lived mem0 client, safe for shared use)
# ---------------------------------------------------------------------------

_session_memory_instance: SessionMemoryService | None = None
_session_memory_init_tried: bool = False


def get_session_memory_instance() -> SessionMemoryService | None:
    """Create a SessionMemoryService if mem0 + credentials available, else None.

    Module-level singleton (mutable state, no ``@lru_cache``).  Uses
    synchronous client creation for DI compatibility.  The
    SessionMemoryService holds a long-lived mem0 client that accepts
    per-call user/project IDs — safe for shared use.

    Exposed as a public name (not ``_``-prefixed) because it is imported
    by :mod:`narrare.writing.deps_writing` — matches the pattern documented
    in :mod:`narrare.kb._feedback_memory_deps` for cross-module
    singleton consumers. Under pyright strict mode, importing a
    ``_``-prefixed name across modules trips ``reportPrivateUsage``;
    the canonical Narrare pattern is to graduate the name to public.

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
        from narrare_core.memory.mem0_client import create_memory_client_sync
        from narrare_core.memory.session_memory_service import SessionMemoryService

        # 1. Check mem0 is installed (encapsulated in core adapter).
        # ``is_mem0_available`` is imported at MODULE LEVEL so the autouse
        # ``_no_real_mem0_clients`` test guard can patch this module's
        # reference (matches the _feedback_memory_deps.py pattern; see
        # ADR-068 Decision 1). Moving it back inside the function body
        # silently breaks the guard.
        if not is_mem0_available():
            logger.info("session_memory_disabled_mem0_not_installed")
            return None

        # 2. Detect provider from env (public API from core adapter).
        # Same module-level import rationale as is_mem0_available above.
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
