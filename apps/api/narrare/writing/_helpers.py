"""Shared helpers for the writing module — extracted per RULE-04.

Contains validation and feedback helpers used across writing sub-services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare.series.series_history_provider import SeriesHistoryProvider
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.models import GenerationRequest
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas import GenerateRequest
    from narrare.writing.schemas_coauthor import ChangeFeedback
    from narrare_core.memory.protocols import FeedbackCollector, SessionMemoryCollector

from narrare.writing._pipeline_request_support import scenes_payload
from narrare_core.memory.models import FeedbackAction, FeedbackEvent
from narrare_core.shared.errors import NotFoundError, ValidationError


async def record_batch_feedback(
    feedback_service: FeedbackCollector | None,
    request_model: GenerationRequest,
    feedback: list[ChangeFeedback],
) -> None:
    """Record batch per-change feedback for co-author (LEARN-001).

    Args:
        feedback_service: Optional feedback collector (no-op if None).
        request_model: The generation request these changes belong to.
        feedback: Per-change feedback items with action and metadata.
    """
    if feedback_service is None:
        return

    for fb in feedback:
        event = FeedbackEvent(
            user_id=request_model.user_id,
            project_id=request_model.novel_id,
            suggestion_id=request_model.id,
            action=FeedbackAction(fb.action),
            intent="write",
            suggestion_text=fb.original,
            context={
                "change_id": fb.change_id,
                "focus": fb.focus,
                "revised": fb.revised,
            },
        )
        await feedback_service.record(event)


# -- Session memory hooks (ADR-045 Decision 8) ----------------------------


async def fetch_cross_session_context(
    session_memory: SessionMemoryCollector | None,
    user_id: UUID,
    novel_id: UUID,
) -> str:
    """Fetch cross-session writing context from mem0 (best-effort, RULE-11).

    Args:
        session_memory: Optional session memory collector (no-op if None).
        user_id: The user whose past sessions to recall.
        novel_id: The novel/project to scope the recall to.

    Returns:
        Formatted context text, or empty string when no memories exist
        or when ``session_memory`` is ``None`` (graceful degradation).
    """
    if session_memory is None:
        return ""
    return await session_memory.get_cross_session_context(user_id, novel_id)


async def record_session_memory(
    session_memory: SessionMemoryCollector | None,
    request_model: GenerationRequest,
    mode: str,
    word_count: int,
) -> None:
    """Record a writing-session summary to mem0 (best-effort, RULE-11).

    Uses ``str(request_model.chapter_id)`` as the structural identifier —
    fetching the actual chapter title would require a dependency the
    service doesn't currently have; the chapter ID is sufficient for
    mem0's semantic search.

    Args:
        session_memory: Optional session memory collector (no-op if None).
        request_model: The completed generation request.
        mode: The generation mode string (e.g. ``"full_draft"``).
        word_count: Number of words in the generated text.
    """
    if session_memory is None:
        return
    await session_memory.record_writing_session(
        request_model.user_id,
        request_model.novel_id,
        mode=mode,
        chapter_title=str(request_model.chapter_id),
        word_count=word_count,
    )


async def prepare_generation_context(
    request_model: GenerationRequest,
    *,
    tone_service: CustomToneService | None,
    relationship_repo: RelationshipRepository | None,
    session_memory: SessionMemoryCollector | None,
    series_history_provider: SeriesHistoryProvider | None = None,
    series_history_budget: int | None = None,
) -> tuple[str | None, str, str, str]:
    """Resolve tone, KB relationships, cross-session + series-history context.

    Combines four independent context-preparation steps into one call
    so ``WritingService.stream_generation`` stays focused on orchestration
    (RULE-04).  All four degrade gracefully when their service is None.

    Args:
        request_model: The persisted generation request.
        tone_service: Optional custom tone service (None → bundled lookup).
        relationship_repo: Optional KB relationship repo (None → empty).
        session_memory: Optional session memory collector (None → empty).
        series_history_provider: Optional series-history provider (None →
            empty — standalone path / backward compatible).
        series_history_budget: Resolved series-history token ceiling
            (ADR-082; ``None`` → provider default).

    Returns:
        Tuple of ``(custom_tone_instructions, kb_relationships_text,
        cross_session_context, series_history)``.
    """
    from narrare.writing._relationship_helpers import fetch_formatted_relationships
    from narrare.writing.tone_resolver import resolve_tone_instructions

    custom_tone = await resolve_tone_instructions(
        tone=request_model.tone,
        user_id=request_model.user_id,
        tone_service=tone_service,
    )
    kb_relationships = await fetch_formatted_relationships(
        relationship_repo,
        request_model.novel_id,
    )
    cross_session = await fetch_cross_session_context(
        session_memory,
        request_model.user_id,
        request_model.novel_id,
    )
    series_history = await fetch_series_history(
        series_history_provider,
        request_model.novel_id,
        token_budget=series_history_budget,
    )
    return custom_tone, kb_relationships.text, cross_session, series_history


async def fetch_series_history(
    provider: SeriesHistoryProvider | None,
    novel_id: UUID,
    *,
    token_budget: int | None = None,
) -> str:
    """Fetch the series-history block (Spec 2 / SERIES-002, ADR-082).

    Args:
        provider: Optional SeriesHistoryProvider (no-op if None).
        novel_id: The novel being generated for.
        token_budget: Resolved series-history ceiling from the
            ContextBudgetResolver (ADR-082 — the API always passes the
            resolved value; the parameter stays explicit per the ADR
            inventory).  ``None`` → provider default (16,000).

    Returns:
        The ``Previously in this series:`` block, or empty string when the
        provider is absent or the novel is standalone (RULE-11 graceful).
    """
    if provider is None:
        return ""
    if token_budget is None:
        return await provider.assemble_series_history(novel_id)
    return await provider.assemble_series_history(novel_id, token_budget=token_budget)


async def get_validated_request(
    repo: GenerationRepository,
    request_id: UUID,
    user_id: str,
) -> GenerationRequest:
    """Fetch and authorize a generation request (extracted per RULE-04).

    Args:
        repo: Generation repository for the lookup.
        request_id: The generation request ID.
        user_id: Authenticated user identifier (access check).

    Raises:
        NotFoundError: If the request does not exist or belongs to another user.

    Returns:
        The validated ``GenerationRequest`` ORM model.
    """
    request_model = await repo.get_by_id(request_id)
    if request_model is None:
        raise NotFoundError("Generation request", identifier=str(request_id))
    if str(request_model.user_id) != user_id:
        raise NotFoundError("Generation request", identifier=str(request_id))
    return request_model


async def verify_chapter_access(
    chapter_repo: ChapterRepository,
    novel_repo: NovelRepository,
    chapter_id: UUID,
    novel_id: UUID,
    user_id: str,
) -> Chapter:
    """Verify caller access to a chapter within a novel (IDOR remediation S5).

    Compound gate composing the EXISTING repository methods (zero repo
    signature changes): the chapter must exist AND belong to the addressed
    novel AND the novel must belong to the caller.  Every failure raises
    the same ``NotFoundError`` so foreign and unknown chapter ids are
    indistinguishable (anti-enumeration, Pattern B).

    Args:
        chapter_repo: Repository for the chapter lookup (``get``).
        novel_repo: Repository for the novel ownership lookup (``get_by_id``).
        chapter_id: The chapter requested by the caller.
        novel_id: The novel the request is scoped to.
        user_id: Authenticated user identifier (``str``; converted to
            ``UUID`` at this boundary).

    Raises:
        NotFoundError: If the chapter does not exist, does not belong to
            the addressed novel, or the novel belongs to another user.

    Returns:
        The authorized ``Chapter`` ORM model.
    """
    chapter = await chapter_repo.get(chapter_id)
    if chapter is None or chapter.novel_id != novel_id:
        raise NotFoundError("Chapter", identifier=str(chapter_id))
    novel = await novel_repo.get_by_id(novel_id, UUID(user_id))
    if novel is None:
        raise NotFoundError("Chapter", identifier=str(chapter_id))
    return chapter


async def create_request_row(
    repo: GenerationRepository,
    chapter_id: UUID,
    novel_id: UUID,
    user_id: str,
    mode: str,
    tone: str,
    scenes: list[dict[str, object]] | None = None,
) -> UUID:
    """Insert a ``generation_request`` row, mapping FK races to 404.

    Shared by the SSE-direct writing services (RULE-04); the
    ``IntegrityError`` catch backstops deletions between gate and insert.

    Args:
        repo: Generation repository (``create_if_no_active``).
        chapter_id: The chapter requested by the caller.
        novel_id: The novel the request is scoped to.
        user_id: Authenticated user id (converted to ``UUID`` here).
        mode: Generation mode string.
        tone: Tone string.
        scenes: Optional structured scene snapshot (PLAN-001 spec §8.2)
            persisted verbatim; ``None`` = legacy scene-less request.

    Raises:
        NotFoundError: If the insert violates a foreign key.

    Returns:
        The id of the newly created generation request.
    """
    try:
        return await repo.create_if_no_active(
            chapter_id, novel_id, UUID(user_id), mode, tone, scenes=scenes
        )
    except IntegrityError as exc:
        raise NotFoundError("Chapter or Novel", identifier=str(chapter_id)) from exc


async def start_generation_request(
    repo: GenerationRepository,
    chapter_repo: ChapterRepository,
    novel_repo: NovelRepository,
    chapter_id: UUID,
    novel_id: UUID,
    user_id: str,
    request: GenerateRequest,
) -> UUID:
    """Gate chapter access, then create the request row (IDOR S6a).

    Order per plan: ``ownership → input → active-conflict``.  Extracted
    from :meth:`WritingService.start_generation` per RULE-04; foreign ≡
    unknown ids raise BEFORE any row is written (no victim pollution,
    no owner-blocking via the unique active index).

    Args:
        repo: Generation repository (``create_if_no_active``).
        chapter_repo: Chapter lookup repo (``get``).
        novel_repo: Novel ownership repo (``get_by_id``).
        chapter_id: The chapter requested by the caller.
        novel_id: The novel the request is scoped to.
        user_id: Authenticated user id (converted to ``UUID`` here).
        request: The generate request payload.

    Raises:
        NotFoundError: No chapter access (foreign ≡ unknown) or FK race.
        ValidationError: If no input source is provided.
        ConflictError: If a generation is already active for the chapter.

    Returns:
        The id of the newly created generation request.
    """
    await verify_chapter_access(chapter_repo, novel_repo, chapter_id, novel_id, user_id)
    validate_generation_input(request)
    return await create_request_row(
        repo,
        chapter_id,
        novel_id,
        user_id,
        request.mode.value,
        request.tone,
        scenes=scenes_payload(request),
    )


def validate_generation_input(request: GenerateRequest) -> None:
    """Ensure at least one of prompt, outline, or auto_continue is set.

    Args:
        request: The generation request to validate.

    Raises:
        ValidationError: If no input source is provided.
    """
    if not request.prompt and not request.outline and not request.auto_continue:
        raise ValidationError(
            "At least one of prompt, outline, or auto_continue must be provided",
            code="MISSING_INPUT",
        )


async def record_feedback(
    feedback_service: FeedbackCollector | None,
    request_model: GenerationRequest,
    action: str,
    *,
    modified_text: str | None = None,
) -> None:
    """Record feedback via FeedbackCollector if available.

    Args:
        feedback_service: Optional feedback collector service.
        request_model: The generation request that generated the feedback.
        action: Feedback action ("accept" or "reject").
        modified_text: Optional user-modified text override.
    """
    if feedback_service is None:
        return
    from narrare_core.memory.models import FeedbackAction, FeedbackEvent

    event = FeedbackEvent(
        user_id=request_model.user_id,
        project_id=request_model.novel_id,
        suggestion_id=request_model.id,
        action=FeedbackAction(action),
        intent="write",
        suggestion_text=modified_text or "",
    )
    await feedback_service.record(event)
