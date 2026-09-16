"""Style-variant support helpers — runtime composite + content builder.

Extracted from ``style_variant_service.py`` (ADR-086 L35) to keep the
service under the 300-line RULE-04 limit after the ``ensure_resolved``
lazy seam was added — mirroring ``_extend_support.py`` (L32) and
``_rewrite_support.py`` (L33) precedents:

- :class:`StyleVariantRuntime` — the frozen first-use composite the DI
  factory's deferred composition hands to the service: the effective
  model config (sampling overrides applied), the routing cascade's
  verbatim credentials, and the tier-wired pipeline;
- :func:`build_variant_content` — the per-stream chapter-content block
  (selection wrapped in ``[SELECTION START]``/``[SELECTION END]``
  markers with optional surrounding context).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StyleVariantRuntime:
    """First-use runtime of a StyleVariantService (ADR-086 M-budget composite).

    Built once by the DI factory's deferred composition
    (``deps_style_variants.py::compose_runtime``) at the service's first
    use — AFTER request validation and the ownership gate — and cached
    for the service's request lifetime
    (:meth:`StyleVariantService.ensure_resolved`).

    Attributes:
        config: Effective model config — the routing cascade's resolved
            config with the variant sampling overrides applied
            (``temperature=0.7``, ``max_tokens=limits.output_limit``).
        api_key: Provider API key from the routing cascade (verbatim).
        base_url: Provider base URL from the routing cascade (verbatim).
        pipeline: WritingPipeline wired with the cascade-resolved
            ``tier_percentages`` and the ADR-082 ``writing_tier_base``
            (variants never inject ``{{series_history}}`` — tiers
            allocate over the full effective total, Decision 6
            standalone semantics for rewrite/coauthor/style-variants).
    """

    config: ResolvedModelConfig
    api_key: str | None
    base_url: str | None
    pipeline: WritingPipeline


def build_variant_content(request: StyleVariantRegenerateRequest) -> str:
    """Build the chapter-content block for a style-variant prompt.

    The source text is wrapped in selection markers so the model
    regenerates exactly that span, with any surrounding context
    prepended/appended for register matching. Extracted from
    ``StyleVariantService.stream_variant`` per RULE-04 (the
    ``ensure_resolved`` lazy seam pushed the service toward its
    300-line limit); behavior is unchanged — only the location moved.
    """
    chapter_content = request.source_text
    if request.context_before or request.context_after:
        parts: list[str] = []
        if request.context_before:
            parts.append(request.context_before)
        parts.append("[SELECTION START]")
        parts.append(request.source_text)
        parts.append("[SELECTION END]")
        if request.context_after:
            parts.append(request.context_after)
        chapter_content = "\n".join(parts)
    return chapter_content


async def mark_variant_failed(
    repo: GenerationRepository,
    draft_processor: DraftProcessor,
    request_id: UUID,
    accumulated: list[str],
    error: Exception,
) -> None:
    """Record a failed style-variant stream: partial draft + failed status + log.

    Extracted from ``StyleVariantService.stream_variant`` per RULE-04
    (the ``ensure_resolved`` lazy seam pushed the service over its
    300-line limit); behavior is unchanged — only the location moved.
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
        "style_variant_stream_failed",
        request_id=str(request_id),
        error=str(error),
    )
