"""Writing-WS handshake — DB-backed ownership gate + runtime resolution.

Extracted from ``router_sessions.py`` per RULE-04 when the IDOR-remediation
S3 ownership gate joined the handshake's DB block (the router sits at the
150-line hard limit — the block must not grow in place). The resolution
order below is SECURITY-PINNED — do not reorder:

1. **Ownership gate** (plan ``2026-08-26-idor-remediation.md``, S3
   follow-up item 4): ``ensure_novel_owned`` scopes the client-supplied
   ``project_id`` to the ticket-derived identity, then the S5 helper
   ``verify_chapter_access`` proves the chapter exists AND belongs to
   that project. Both run BEFORE any project-keyed read: an unvalidated
   ``project_id`` would otherwise auto-create a settings row (foreign
   project) or surface an FK ``IntegrityError`` 500-oracle (unknown
   project), and a foreign chapter would stream another user's prose
   (cross-tenant exfiltration). ``NotFoundError`` propagates to the
   router → close 4001; foreign ≡ unknown by construction
   (anti-enumeration).
2. **Token limits** — project → user → config cascade.
3. **Model routing** — WRITE-intent resolution (RULE-18).

The deliberate double novel lookup (``ensure_novel_owned`` plus the S5
helper's internal check) mirrors the factory N1 pattern: the project
scope is rejected on its own BEFORE any chapter semantics — correctness
over micro-optimization (plan S5).

All repository/service imports are CALL-TIME so hermetic unit tests keep
the established patch points (``narrare.novels.repository.NovelRepository``,
``narrare.chapters.repository.ChapterRepository`` — see
``novels/ownership.py`` for the patch-point rationale).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare_core.llm.model_config import ResolvedModelConfig


async def resolve_ws_session_config(
    user_id: str,
    chapter_id: UUID,
    project_id: UUID,
) -> tuple[ResolvedModelConfig, TokenLimitOverrides]:
    """Gate access, then resolve handler config + limits for one WS session.

    Args:
        user_id: Ticket-derived caller identity (ADR-084; ``str`` at the
            route boundary).
        chapter_id: The chapter the session is opened on (path param).
        project_id: The caller-supplied project scope — presence-checked
            by the router before this call.

    Raises:
        NotFoundError: The project or chapter is unknown or owned by
            another user — indistinguishable by design (anti-enumeration).

    Returns:
        ``(config, limits)``: the WRITE-intent model config with the
        handshake temperature and output-limit cap, and the resolved
        token-limit overrides (``ws_timeout`` feeds the idle timeout).
    """
    from dataclasses import replace as dataclass_replace

    from narrare._app.config import get_settings
    from narrare._app.database import get_async_session
    from narrare._app.dependencies_services import get_model_routing_resolver
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing._helpers import verify_chapter_access
    from narrare.writing.deps_ownership import ensure_novel_owned
    from narrare_core.llm.intents import LLMIntent

    _session_gen = get_async_session()
    session = await _session_gen.__anext__()
    try:
        # 1. Ownership gate — BEFORE any project-keyed settings/routing
        #    read (foreign → transient settings row; unknown → FK oracle).
        await ensure_novel_owned(session, user_id, project_id)
        await verify_chapter_access(
            ChapterRepository(session),
            NovelRepository(session),
            chapter_id,
            project_id,
            user_id,
        )
        # 2. Token limits (project → user → config cascade).
        token_limits_service = TokenLimitsService(
            user_repo=UserTokenLimitsRepository(session),
            project_repo=ProjectTokenLimitsRepository(session),
            config=get_settings(),
        )
        limits = await token_limits_service.get_resolved_limits(
            user_id=user_id,
            project_id=str(project_id),
        )
        # 3. Model config per-user via routing resolver (RULE-18).
        resolver = get_model_routing_resolver(session)
        resolved = await resolver.resolve(
            LLMIntent.WRITE,
            UUID(user_id),
            project_id,
        )
        config = dataclass_replace(
            resolved.config,
            temperature=0.7,
            max_tokens=limits.output_limit,
        )
    finally:
        await _session_gen.aclose()
    return config, limits
