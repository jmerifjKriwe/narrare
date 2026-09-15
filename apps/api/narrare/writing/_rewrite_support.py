"""Rewrite support helpers — runtime composite + prompt-input builders.

Extracted from ``rewrite_service.py`` (ADR-086 L33) to keep the service
under the 300-line RULE-04 limit after the ``ensure_resolved`` lazy seam
was added — mirroring ``_suggest_support.py`` (L36 precedent):

- :class:`RewriteRuntime` — the frozen first-use composite the DI
  factory's deferred composition hands to the service: the effective
  model config (sampling overrides applied), the routing cascade's
  verbatim credentials, and the tier-wired pipeline;
- :func:`build_pipeline_request` — the core generation request for the
  REWRITE mode (pure mapping, no I/O);
- :func:`build_rewrite_content` — the chapter-content block with the
  ``[SELECTION START]/[SELECTION END]`` context markers (pure mapping,
  no I/O).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_rewrite import RewriteRequest
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.models import GenerationRequest as CoreGenerationRequest
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RewriteRuntime:
    """First-use runtime of a RewriteService (ADR-086 M-budget composite).

    Built once by the DI factory's deferred composition
    (``deps_rewrite.py::compose_runtime``) at the service's first use —
    AFTER request validation and the ownership gate — and cached for the
    service's request lifetime (:meth:`RewriteService.ensure_resolved`).

    Attributes:
        config: Effective model config — the routing cascade's resolved
            config with the rewrite sampling overrides applied
            (``temperature=0.7``, ``max_tokens=limits.output_limit``).
        api_key: Provider API key from the routing cascade (verbatim).
        base_url: Provider base URL from the routing cascade (verbatim).
        pipeline: WritingPipeline wired with the cascade-resolved
            ``tier_percentages`` and the ADR-082 ``writing_tier_base``.
    """

    config: ResolvedModelConfig
    api_key: str | None
    base_url: str | None
    pipeline: WritingPipeline


def build_pipeline_request(
    request_id: UUID,
    chapter_id: UUID,
    novel_id: UUID,
    user_id: str,
    request: RewriteRequest,
) -> CoreGenerationRequest:
    """Build the core generation request for a rewrite stream.

    Args:
        request_id: ``generation_request`` row id (created by the repo).
        chapter_id: Chapter containing the selection to rewrite.
        novel_id: Novel the chapter belongs to.
        user_id: Authenticated user identifier.
        request: Rewrite-specific parameters (tone, language, ...).

    Returns:
        Core ``GenerationRequest`` pinned to ``GenerationMode.REWRITE``;
        rewrites never use word targets (``word_target=0``).
    """
    from narrare_core.writing._enums import GenerationMode
    from narrare_core.writing.models import GenerationRequest as CoreGenerationRequest

    return CoreGenerationRequest(
        id=request_id,
        chapter_id=chapter_id,
        project_id=novel_id,
        user_id=UUID(user_id),
        mode=GenerationMode.REWRITE,
        tone=request.tone,
        word_target=0,  # Rewrite doesn't use word targets
        writing_language=request.language,
    )


@dataclass(frozen=True)
class RewriteStreamInputs:
    """Auxiliary prompt inputs for a rewrite stream (RULE-04 bundle).

    Assembled once per stream by :func:`build_rewrite_stream_inputs` —
    everything the pipeline call needs beyond the runtime and the core
    request.

    Attributes:
        chapter_content: Selection text with optional context markers.
        custom_tone_instructions: Resolved custom-tone instructions
            (``None`` when unresolved).
        rewrite_mode: Rewrite mode value (``tone``/``style``/...).
        custom_instructions: Free-form user instructions (empty when none).
        kb_relationships: Formatted KB relationship text (FIND-009).
    """

    chapter_content: str
    custom_tone_instructions: str | None
    rewrite_mode: str
    custom_instructions: str
    kb_relationships: str


async def build_rewrite_stream_inputs(
    *,
    request: RewriteRequest,
    user_id: UUID,
    tone_service: CustomToneService | None,
    relationship_repo: RelationshipRepository | None,
    novel_id: UUID,
) -> RewriteStreamInputs:
    """Assemble the auxiliary prompt inputs for a rewrite stream.

    Resolves the custom tone instructions (ADR tone cascade), the
    rewrite-mode inputs, and the formatted KB relationships (FIND-009).
    Extracted from ``RewriteService.stream_rewrite`` per RULE-04 (the
    ``ensure_resolved`` lazy seam pushed the service over its 300-line
    limit); behavior is unchanged — only the location moved.
    """
    from narrare.writing._relationship_helpers import fetch_formatted_relationships
    from narrare.writing.tone_resolver import resolve_tone_instructions

    custom_tone_instructions = await resolve_tone_instructions(
        tone=request.tone,
        user_id=user_id,
        tone_service=tone_service,
    )
    kb_relationships = await fetch_formatted_relationships(
        relationship_repo,
        novel_id,
    )
    return RewriteStreamInputs(
        chapter_content=build_rewrite_content(request),
        custom_tone_instructions=custom_tone_instructions,
        rewrite_mode=request.mode.value,
        custom_instructions=request.custom_instructions or "",
        kb_relationships=kb_relationships.text,
    )


async def mark_rewrite_failed(
    repo: GenerationRepository,
    draft_processor: DraftProcessor,
    request_id: UUID,
    accumulated: list[str],
    error: Exception,
) -> None:
    """Record a failed rewrite stream: partial draft + failed status + log.

    Extracted from ``RewriteService.stream_rewrite`` per RULE-04 (the
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
        "rewrite_stream_failed",
        request_id=str(request_id),
        error=str(error),
    )


def build_rewrite_content(request: RewriteRequest) -> str:
    """Build the chapter-content block for a rewrite prompt.

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
