"""Extend support helpers — runtime composite + failure handler.

Extracted from ``extend_service.py`` (ADR-086 L32) to keep the service
under the 300-line RULE-04 limit after the ``ensure_resolved`` lazy seam
was added — mirroring ``_rewrite_support.py`` (L33 precedent):

- :class:`ExtendRuntime` — the frozen first-use composite the DI
  factory's deferred composition hands to the service: the effective
  model config (sampling overrides applied), the routing cascade's
  verbatim credentials, and the tier-wired pipeline;
- :func:`build_extend_stream_inputs` — the per-stream prompt inputs
  (content block with the ``[CONTINUE FROM HERE]`` marker, resolved
  custom-tone instructions, formatted KB relationships);
- :func:`mark_extend_failed` — the failed-status recorder for a broken
  stream (partial draft + status + log); behavior unchanged, only the
  location moved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas import ExtendRequest
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ExtendRuntime:
    """First-use runtime of an ExtendService (ADR-086 M-budget composite).

    Built once by the DI factory's deferred composition
    (``deps_extend.py::compose_runtime``) at the service's first use —
    AFTER request validation and the ownership gate — and cached for the
    service's request lifetime (:meth:`ExtendService.ensure_resolved`).

    Attributes:
        config: Effective model config — the routing cascade's resolved
            config with the extend sampling overrides applied
            (``temperature=0.7``, ``max_tokens=limits.output_limit``).
        api_key: Provider API key from the routing cascade (verbatim).
        base_url: Provider base URL from the routing cascade (verbatim).
        pipeline: WritingPipeline wired with the cascade-resolved
            ``tier_percentages`` and the ADR-082 ``writing_tier_base``
            (extend never injects ``{{series_history}}`` — tiers
            allocate over the full effective total, Decision 6
            standalone semantics).
    """

    config: ResolvedModelConfig
    api_key: str | None
    base_url: str | None
    pipeline: WritingPipeline


@dataclass(frozen=True)
class ExtendStreamInputs:
    """Auxiliary prompt inputs for an extend stream (RULE-04 bundle).

    Assembled once per stream by :func:`build_extend_stream_inputs` —
    everything the pipeline call needs beyond the runtime and the core
    request.

    Attributes:
        chapter_content: Pre-cursor text with the continuation marker
            and optional forward context.
        custom_tone_instructions: Resolved custom-tone instructions
            (``None`` when unresolved).
        kb_relationships: Formatted KB relationship text (FIND-009).
    """

    chapter_content: str
    custom_tone_instructions: str | None
    kb_relationships: str


async def build_extend_stream_inputs(
    *,
    request: ExtendRequest,
    user_id: UUID,
    tone_service: CustomToneService | None,
    relationship_repo: RelationshipRepository | None,
    novel_id: UUID,
) -> ExtendStreamInputs:
    """Assemble the auxiliary prompt inputs for an extend stream.

    Resolves the custom tone instructions (ADR tone cascade) and the
    formatted KB relationships (FIND-009), and builds the chapter-
    content block (pre-cursor text + ``[CONTINUE FROM HERE]`` marker +
    optional forward context). Extracted from
    ``ExtendService.stream_extend`` per RULE-04 (the ``ensure_resolved``
    lazy seam pushed the service over its 300-line limit); behavior is
    unchanged — only the location moved.
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
    return ExtendStreamInputs(
        chapter_content=build_extend_content(request),
        custom_tone_instructions=custom_tone_instructions,
        kb_relationships=kb_relationships.text,
    )


def build_extend_content(request: ExtendRequest) -> str:
    """Build the chapter-content block for an extend prompt.

    The pre-cursor text is the primary content; the continuation point
    is marked so the model extends from the cursor, with any forward
    context appended after the marker.
    """
    chapter_content = request.text_before
    if request.text_after:
        chapter_content += "\n[CONTINUE FROM HERE]\n" + request.text_after
    else:
        chapter_content += "\n[CONTINUE FROM HERE]\n"
    return chapter_content


async def mark_extend_failed(
    repo: GenerationRepository,
    draft_processor: DraftProcessor,
    request_id: UUID,
    accumulated: list[str],
    error: Exception,
) -> None:
    """Record a failed extend stream: partial draft + failed status + log.

    Extracted from ``ExtendService.stream_extend`` per RULE-04 (the
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
        "extend_stream_failed",
        request_id=str(request_id),
        error=str(error),
    )
