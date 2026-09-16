"""Writing support — first-use runtime composite + novel-context helper.

Extracted (ADR-086 L37) to keep ``service.py`` under the 300-line
RULE-04 limit after the ``ensure_resolved`` lazy seam was added —
mirroring ``_coauthor_support.py`` (L31 precedent):

- :class:`WritingRuntime` — the frozen first-use composite the DI
  factory's deferred composition hands to the service: the effective
  model config (sampling overrides applied), the routing cascade's
  verbatim credentials, the tier-wired pipeline, and the ADR-082
  series-history ceiling;
- :func:`resolve_novel_context` — the ownership-aware novel title/genre
  supply for prompt context (RULE-11 degradation), extracted from
  ``WritingService.stream_generation`` per RULE-04; behavior unchanged —
  only the location moved;
- :func:`build_stream_inputs` — the per-stream context assembly
  (tone / KB relationships / cross-session + series-history context,
  then the novel supply), extracted from ``WritingService.stream_generation``
  per RULE-04 (the ``ensure_resolved`` lazy seam pushed the service over
  its 300-line limit) — mirroring ``build_coauthor_stream_inputs``
  (L31 precedent); behavior unchanged — only the location moved;
- :func:`build_generation_stats_response` — the pure repo-row →
  response mapping for the stats fallback path, extracted per RULE-04.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.writing._helpers import prepare_generation_context

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare.series.series_history_provider import SeriesHistoryProvider
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.models import GenerationRequest
    from narrare.writing.schemas import GenerationStatsResponse
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.memory.protocols import SessionMemoryCollector
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class WritingRuntime:
    """First-use runtime of a WritingService (ADR-086 M-budget composite).

    Built once by the DI factory's deferred composition
    (``deps_writing.py::compose_runtime``) at the service's first use —
    AFTER the request-row ownership gate — and cached for the service's
    request lifetime (:meth:`WritingService.ensure_resolved`).

    Attributes:
        config: Effective model config — the routing cascade's resolved
            config with the writing sampling overrides applied
            (``temperature=0.7``, ``max_tokens=limits.output_limit``;
            SUGGEST intent: ``temperature=0.3`` +
            ``SUGGEST_MAX_TOKENS``).
        api_key: Provider API key from the routing cascade (verbatim).
        base_url: Provider base URL from the routing cascade (verbatim).
        pipeline: WritingPipeline wired with the cascade-resolved
            ``tier_percentages`` and the ADR-082 ``writing_tier_base``.
        series_history_budget: ADR-082 series-history token ceiling
            (``budgets.series_history``; ``None`` → provider default).
    """

    config: ResolvedModelConfig
    api_key: str | None
    base_url: str | None
    pipeline: WritingPipeline
    series_history_budget: int | None


async def resolve_novel_context(
    novel_repo: NovelRepository,
    novel_id: UUID,
    user_id: str,
) -> tuple[str, str]:
    """Ownership-aware novel supply for title/genre prompt context.

    Sibling-service resolution: ``get_by_id(novel_id, user)``.
    RULE-11: any fetch failure degrades to empty strings — logged, and
    the draft proceeds without novel context. Extracted from
    ``WritingService.stream_generation`` per RULE-04 (the
    ``ensure_resolved`` lazy seam pushed the service over its 300-line
    limit); behavior is unchanged — only the location moved.
    """
    project_title = ""
    genre = ""
    try:
        novel = await novel_repo.get_by_id(novel_id, UUID(user_id))
    except Exception as exc:
        logger.warning(
            "novel_context_fetch_failed",
            novel_id=str(novel_id),
            error=str(exc),
        )
    else:
        if novel is not None:
            project_title = novel.title or ""
            genre = novel.genre or ""
    return project_title, genre


@dataclass(frozen=True)
class WritingStreamInputs:
    """Auxiliary prompt inputs for a writing stream (RULE-04 bundle).

    Assembled once per stream by :func:`build_stream_inputs` —
    everything the pipeline call needs beyond the runtime and the core
    request.

    Attributes:
        custom_tone_instructions: Resolved custom-tone block (None if
            no tone service is wired — RULE-11 graceful).
        kb_relationships: Formatted KB relationship text (FIND-009).
        cross_session_context: Cross-session memory context (ADR-045).
        series_history: Prior-bands summary block (Spec 2; empty for
            standalone novels).
        project_title: Novel title for prompt context (degraded: "").
        genre: Novel genre for prompt context (degraded: "").
    """

    custom_tone_instructions: str | None
    kb_relationships: str
    cross_session_context: str
    series_history: str
    project_title: str
    genre: str


async def build_stream_inputs(
    request_model: GenerationRequest,
    *,
    tone_service: CustomToneService | None,
    relationship_repo: RelationshipRepository | None,
    session_memory: SessionMemoryCollector | None,
    series_history_provider: SeriesHistoryProvider | None,
    series_history_budget: int | None,
    novel_repo: NovelRepository,
    user_id: str,
) -> WritingStreamInputs:
    """Assemble the auxiliary prompt inputs for a writing stream.

    Resolves tone, KB relationships, cross-session + series-history
    context (via the ``_helpers`` RULE-04 bundle; the series-history
    ceiling is a token-limits cascade output — supplied by the composed
    runtime, ADR-086 L37), then the ownership-aware novel title/genre
    supply. Extracted from ``WritingService.stream_generation`` per
    RULE-04; behavior is unchanged — only the location moved.
    """
    (
        custom_tone_instructions,
        kb_text,
        cross_session_context,
        series_history,
    ) = await prepare_generation_context(
        request_model,
        tone_service=tone_service,
        relationship_repo=relationship_repo,
        session_memory=session_memory,
        series_history_provider=series_history_provider,
        series_history_budget=series_history_budget,
    )
    project_title, genre = await resolve_novel_context(novel_repo, request_model.novel_id, user_id)
    return WritingStreamInputs(
        custom_tone_instructions=custom_tone_instructions,
        kb_relationships=kb_text,
        cross_session_context=cross_session_context,
        series_history=series_history,
        project_title=project_title,
        genre=genre,
    )


def build_generation_stats_response(
    stats: Mapping[str, Any],
) -> GenerationStatsResponse:
    """Map a repo stats row onto the API response (pure mapping).

    Fallback path of ``WritingService.get_stats`` when no StatsService
    is wired. Extracted per RULE-04 (the ``ensure_resolved`` lazy seam
    pushed the service over its 300-line limit); behavior unchanged —
    only the location moved.
    """
    from narrare.writing.schemas import GenerationStatsResponse

    return GenerationStatsResponse(
        total_generations=int(stats["total_generations"]),
        success_rate=float(stats["success_rate"]),
        avg_tokens=float(stats["avg_tokens"]),
        avg_word_count=float(stats["avg_word_count"]),
        most_used_model=stats.get("most_used_model"),
    )
