"""Writing-WS handshake — DB-backed ownership gate + lazy resolution wiring.

Extracted from ``router_sessions.py`` per RULE-04 when the IDOR-remediation
S3 ownership gate joined the handshake's DB block (the router sits at the
150-line hard limit — the block must not grow in place). The resolution
order below is SECURITY-PINNED — do not reorder:

1. **Reattach admission (reconnects only)** — when the client presents
   a ``session_id``, the pure-data session-ownership validation runs
   FIRST and answers with the typed ``recovery_failed`` reason
   (:class:`ReattachRejectedError` → router frame + close 4404): the
   client drops stale session state only on that typed frame, whereas
   the gate's generic 4001 close would blind-loop the frontend socket
   reconnect on the same stale tuple (ADR-052). Fresh sessions skip it.
2. **Ownership gate** (plan ``2026-08-26-idor-remediation.md``, S3
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
3. **Token limits** — project → user → config cascade (accepted ADR-086
   residual: ``ws_timeout`` feeds the handler idle timeout and the tier
   overrides thread into the assembler, both needed at bootstrap).
4. **Model routing** — WRITE-intent resolution wired LAZILY (ADR-086
   L39): the handshake returns a ``LazyModelResolution``; the routing
   cascade runs at first use (first turn / first interview draft), after
   validation-relevant gates, on a short-lived session of its own.

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
    from narrare._app.dependencies_services import ModelResolution
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.writing.contracts import WritingSessionControlProtocol
    from narrare.writing.session_control_contracts import ReattachSessionResult
    from narrare_core.llm.model_routing import ResolvedModel


class ReattachRejectedError(Exception):
    """A reconnect's reattach validation failed — carry the typed DTO.

    Raised by :func:`resolve_ws_session_config` when the pre-gate
    reattach probe rejects (not-found / expired / ownership mismatch).
    The router converts ``payload`` (control-service DTO) into the
    public ``recovery_failed`` frame + close 4404 — the handler's
    reject convention (ADR-052).
    """

    def __init__(self, payload: ReattachSessionResult) -> None:
        super().__init__(payload.get("kind", "unknown"))
        self.payload = payload


async def resolve_ws_session_config(
    user_id: str,
    chapter_id: UUID,
    project_id: UUID,
    *,
    session_id: UUID | None = None,
    control_service: WritingSessionControlProtocol | None = None,
) -> tuple[ModelResolution, TokenLimitOverrides]:
    """Gate access, then wire the lazy model resolution + resolve limits.

    Args:
        user_id: Ticket-derived caller identity (ADR-084; ``str`` at the
            route boundary).
        chapter_id: The chapter the session is opened on (path param).
        project_id: The caller-supplied project scope — presence-checked
            by the router before this call.
        session_id: Reconnect-only — the session to reattach to. When
            present (with ``control_service``), the reattach admission
            probe runs before the ownership gate.
        control_service: Session-control service used for the reattach
            probe (validated via ``WritingSessionControlProtocol``).

    Raises:
        ReattachRejectedError: The reattach probe rejected the reconnect —
            the caller must answer with the typed ``recovery_failed``
            frame instead of proceeding to the gate.
        NotFoundError: The project or chapter is unknown or owned by
            another user — indistinguishable by design (anti-enumeration).

    Returns:
        ``(model_resolution, limits)``: the lazily-wired WRITE-intent
        resolution (ADR-086 L39 — the routing cascade runs at first use,
        with the handshake freeze applied by ``_ws_turn_support``) and the
        resolved token-limit overrides (``ws_timeout`` feeds the idle
        timeout).
    """
    from narrare._app.config import get_settings
    from narrare._app.database import get_async_session
    from narrare._app.dependencies_services import LazyModelResolution
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing._helpers import verify_chapter_access
    from narrare.writing.deps_ownership import ensure_novel_owned
    from narrare.writing.session_control_contracts import ReattachOutcomeKind
    from narrare_core.llm.intents import LLMIntent

    # 1. Reattach admission (reconnects only, ADR-052): the typed
    #    recovery answer must preempt the ownership gate — a mismatched
    #    owner tuple would otherwise surface as the gate's generic 4001
    #    (chapter ∉ claimed project), leaving the client's stale
    #    session state blind-looping its reconnect. Pure-data (cache)
    #    validation via the control service; the handler re-runs the
    #    full reattach with the transport sink once the gate has passed.
    if session_id is not None and control_service is not None:
        outcome = await control_service.reattach_session(
            session_id,
            UUID(user_id),
            project_id,
        )
        if outcome.get("kind") != ReattachOutcomeKind.RECOVERED:
            raise ReattachRejectedError(outcome)

    _session_gen = get_async_session()
    session = await _session_gen.__anext__()
    try:
        # 2. Ownership gate — BEFORE any project-keyed settings/routing
        #    read (foreign → transient settings row; unknown → FK oracle).
        await ensure_novel_owned(session, user_id, project_id)
        await verify_chapter_access(
            ChapterRepository(session),
            NovelRepository(session),
            chapter_id,
            project_id,
            user_id,
        )
        # 3. Token limits (project → user → config cascade) — accepted
        #    ADR-086 residual at bootstrap (ws_timeout feeds the handler).
        token_limits_service = TokenLimitsService(
            user_repo=UserTokenLimitsRepository(session),
            project_repo=ProjectTokenLimitsRepository(session),
            config=get_settings(),
        )
        limits = await token_limits_service.get_resolved_limits(
            user_id=user_id,
            project_id=str(project_id),
        )
    finally:
        await _session_gen.aclose()

    # 4. Model routing per-user (RULE-18) — wired LAZILY (ADR-086 L39).
    #    The handshake session is closed by first use (a WebSocket
    #    connection has no request-scoped session), so the factory
    #    sources its OWN short-lived session at resolve time — the
    #    WsWritingContextAssembler session precedent.
    user_uuid = UUID(user_id)

    async def resolve_write_intent() -> ResolvedModel:
        from narrare._app.database import get_async_session
        from narrare._app.dependencies_services import get_model_routing_resolver

        resolve_gen = get_async_session()
        resolve_session = await resolve_gen.__anext__()
        try:
            resolver = get_model_routing_resolver(resolve_session)
            return await resolver.resolve(LLMIntent.WRITE, user_uuid, project_id)
        finally:
            await resolve_gen.aclose()

    model_resolution = LazyModelResolution(resolve_write_intent)
    return model_resolution, limits
