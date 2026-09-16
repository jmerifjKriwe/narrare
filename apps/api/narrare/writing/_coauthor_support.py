"""Co-author support helpers — runtime composite + prompt-input builders.

Extracted from ``coauthor_service.py`` (ADR-086 L31) to keep the service
under the 300-line RULE-04 limit after the ``ensure_resolved`` lazy seam
was added — mirroring ``_rewrite_support.py`` (L33 precedent):

- :class:`CoAuthorRuntime` — the frozen first-use composite the DI
  factory's deferred composition hands to the service: the effective
  model config (sampling overrides applied), the routing cascade's
  verbatim credentials, the tier-wired pipeline, and the SET-005
  ``max_selection_words`` limit;
- :func:`build_pipeline_request` — the core generation request for the
  CO_AUTHOR mode (pure mapping, no I/O);
- :func:`build_coauthor_content` — the chapter-content block with the
  ``[SELECTION START]/[SELECTION END]`` context markers (pure mapping,
  no I/O);
- :func:`mark_coauthor_failed` — the failed-status recorder for a
  broken stream (partial draft + status + log);
- :func:`mark_coauthor_completed` — the completion recorder for a
  finished stream (cleaned word count + completed status + LEARN-001
  feedback); both extracted per RULE-04, behavior unchanged — only the
  location moved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.writing._helpers import record_feedback

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_coauthor import CoAuthorRequest
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.llm.result import TokenUsage
    from narrare_core.memory.protocols import FeedbackCollector
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.models import GenerationRequest as CoreGenerationRequest
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CoAuthorRuntime:
    """First-use runtime of a CoAuthorService (ADR-086 M-budget composite).

    Built once by the DI factory's deferred composition
    (``deps_coauthor.py::compose_runtime``) at the service's first use —
    AFTER request validation and the ownership gate — and cached for the
    service's request lifetime (:meth:`CoAuthorService.ensure_resolved`).

    Attributes:
        config: Effective model config — the routing cascade's resolved
            config with the co-author sampling overrides applied
            (``temperature=0.7``, ``max_tokens=limits.output_limit``).
        api_key: Provider API key from the routing cascade (verbatim).
        base_url: Provider base URL from the routing cascade (verbatim).
        pipeline: WritingPipeline wired with the cascade-resolved
            ``tier_percentages`` and the ADR-082 ``writing_tier_base``.
        max_selection_words: SET-005 cascade limit (user → project →
            env → code default) for the selection-length validation.
    """

    config: ResolvedModelConfig
    api_key: str | None
    base_url: str | None
    pipeline: WritingPipeline
    max_selection_words: int


def build_pipeline_request(
    request_id: UUID,
    chapter_id: UUID,
    novel_id: UUID,
    user_id: str,
    request: CoAuthorRequest,
) -> CoreGenerationRequest:
    """Build the core generation request for a co-author stream.

    Args:
        request_id: ``generation_request`` row id (created by the repo).
        chapter_id: Chapter containing the selection to revise.
        novel_id: Novel the chapter belongs to.
        user_id: Authenticated user identifier.
        request: Co-author-specific parameters (focus, tone, language).

    Returns:
        Core ``GenerationRequest`` pinned to ``GenerationMode.CO_AUTHOR``;
        co-author never uses word targets (``word_target=0``).
    """
    from narrare_core.writing._enums import GenerationMode
    from narrare_core.writing.models import GenerationRequest as CoreGenerationRequest

    return CoreGenerationRequest(
        id=request_id,
        chapter_id=chapter_id,
        project_id=novel_id,
        user_id=UUID(user_id),
        mode=GenerationMode.CO_AUTHOR,
        tone=request.tone,
        word_target=0,  # Co-author doesn't use word targets
        writing_language=request.language,
    )


def build_coauthor_content(request: CoAuthorRequest) -> str:
    """Build the chapter-content block for a co-author prompt.

    The selection text is the primary content; optional surrounding
    context is wrapped in explicit ``[SELECTION START]/[SELECTION END]``
    markers so the model can tell selection and context apart.
    """
    if not request.context_before and not request.context_after:
        return request.selection_text

    parts: list[str] = []
    if request.context_before:
        parts.append(request.context_before)
    parts.append("[SELECTION START]")
    parts.append(request.selection_text)
    parts.append("[SELECTION END]")
    if request.context_after:
        parts.append(request.context_after)
    return "\n".join(parts)


@dataclass(frozen=True)
class CoAuthorStreamInputs:
    """Auxiliary prompt inputs for a co-author stream (RULE-04 bundle).

    Assembled once per stream by :func:`build_coauthor_stream_inputs` —
    everything the pipeline call needs beyond the runtime and the core
    request.

    Attributes:
        chapter_content: Selection text with optional context markers.
        kb_relationships: Formatted KB relationship text (FIND-009).
    """

    chapter_content: str
    kb_relationships: str


async def build_coauthor_stream_inputs(
    *,
    request: CoAuthorRequest,
    relationship_repo: RelationshipRepository | None,
    novel_id: UUID,
) -> CoAuthorStreamInputs:
    """Assemble the auxiliary prompt inputs for a co-author stream.

    Builds the selection-marker content block and fetches the formatted
    KB relationships (FIND-009). Extracted from
    ``CoAuthorService.stream_coauthor`` per RULE-04 (the
    ``ensure_resolved`` lazy seam pushed the service over its 300-line
    limit); behavior is unchanged — only the location moved.
    """
    from narrare.writing._relationship_helpers import fetch_formatted_relationships

    kb_relationships = await fetch_formatted_relationships(
        relationship_repo,
        novel_id,
    )
    return CoAuthorStreamInputs(
        chapter_content=build_coauthor_content(request),
        kb_relationships=kb_relationships.text,
    )


async def mark_coauthor_failed(
    repo: GenerationRepository,
    draft_processor: DraftProcessor,
    request_id: UUID,
    accumulated: list[str],
    error: Exception,
    chapter_id: UUID,
) -> None:
    """Record a failed co-author stream: partial draft + failed status + log.

    Extracted from ``CoAuthorService.stream_coauthor`` per RULE-04 (the
    ``ensure_resolved`` lazy seam pushed the service over its 300-line
    limit); behavior is unchanged — only the location moved.
    """
    partial = draft_processor.process(
        "".join(accumulated),
        is_partial=True,
    )
    partial_words = len(partial.split()) if partial else 0
    await repo.update_status(
        request_id,
        "failed",
        error_message=str(error),
        word_count=partial_words,
        completed_at=datetime.now(UTC),
    )
    logger.error(
        "coauthor_stream_failed",
        request_id=str(request_id),
        chapter_id=str(chapter_id),
        error=str(error),
    )


async def mark_coauthor_completed(
    repo: GenerationRepository,
    draft_processor: DraftProcessor,
    request_id: UUID,
    accumulated: list[str],
    final_text: str,
    usage: TokenUsage | None,
    feedback: FeedbackCollector | None,
) -> None:
    """Record a completed co-author stream: cleaned word count + status.

    Extracted from ``CoAuthorService.stream_coauthor`` per RULE-04 (the
    ``ensure_resolved`` lazy seam pushed the service over its 300-line
    limit); behavior is unchanged — only the location moved.
    """
    raw_text = "".join(accumulated) + final_text
    cleaned = draft_processor.process(raw_text)
    word_count = len(cleaned.split())
    await repo.update_status(
        request_id,
        "completed",
        tokens_used=usage.total_tokens if usage else 0,
        word_count=word_count,
        completed_at=datetime.now(UTC),
    )

    # Record feedback (LEARN-001 integration)
    if feedback is None:
        return
    request_model = await repo.get_by_id(request_id)
    if request_model is not None:
        await record_feedback(
            feedback,
            request_model,
            "accept",
        )
