"""Author-voice agent invocation helper (Mode 1 + one LLM call).

Extracted from ``author_voice_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the single responsibility of running the
:class:`AuthorVoiceAgent` with the resolved prompt, formatted prose excerpt,
and precomputed metrics.

The chapter prose + precomputed metrics flow as runtime content in the agent
run prompt (user channel, RULE-02a category 3). No system/task instruction is
inlined — the governed ``author_voice`` template IS the system prompt
(resolved Mode 1 by :func:`narrare.analysis.author_voice_prompt.
resolve_author_voice_prompt`).

See:
    ADR-074 — Author Voice Storage Contract (binding boundary — descriptive
        output only; the agent never produces metrics).
    ADR-054 — Mode 1 prompt resolution.
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import DefaultRunLimitResolver

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.agents.author_voice_types import AuthorVoiceOutput
    from narrare_core.analysis.author_metrics import AuthorMetrics
    from narrare_core.kb.schemas.character import VoiceMetrics
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


def _truncate_prose(prose: str, *, max_chars: int = 12_000) -> str:
    """Truncate chapter prose to a model-friendly excerpt.

    The deterministic metrics are computed over the FULL prose upstream; the
    agent only needs a representative excerpt to interpret qualitatively
    (binding boundary — measurement is deterministic, the agent interprets).
    12k chars is a conservative budget that leaves room for the metrics
    summary + the governed system prompt within a typical analysis model's
    context window.
    """
    if len(prose) <= max_chars:
        return prose
    return prose[:max_chars]


def format_voice_metrics_summary(metrics: VoiceMetrics) -> str:
    """Format voice-generic deterministic metrics for the model.

    The agent interprets these (never recomputes them — ADR-074 binding).
    Voice-generic metrics are computed by
    :meth:`VoiceMetricsAnalyzer.analyze_text` over the author's full prose.
    """
    return (
        f"avg_sent_len={metrics.avg_sentence_length}, "
        f"sent_len_std={metrics.sentence_length_std}, "
        f"ttr={metrics.type_token_ratio}, "
        f"avg_syllables={metrics.avg_syllables_per_word}, "
        f"contraction_rate={metrics.contraction_rate}"
    )


def format_author_metrics_summary(metrics: AuthorMetrics) -> str:
    """Format author-specific prose-level metrics for the model.

    The agent interprets these (never recomputes them — ADR-074 binding +
    ADR-021 determinism). Author-specific metrics are computed by
    :class:`AuthorMetricsAnalyzer` over the author's full prose.
    """
    return (
        f"dialogue_ratio={metrics.dialogue_ratio}, "
        f"description_density={metrics.description_density}, "
        f"action_introspection_ratio={metrics.action_introspection_ratio}, "
        f"metaphor_density={metrics.metaphor_density}"
    )


def build_author_voice_run_prompt(
    prose_excerpt: str,
    voice_metrics_summary: str,
    author_metrics_summary: str,
) -> str:
    """Build the agent run prompt (user channel) from runtime content.

    The prose excerpt + precomputed metrics are category-3 runtime content
    (RULE-02a) — never feature-task framing. No system/task instruction is
    inlined; the governed template IS the system prompt.
    """
    parts = [f"Prose:\n{prose_excerpt}"]
    if voice_metrics_summary:
        parts.append(f"\nVoice metrics:\n{voice_metrics_summary}")
    if author_metrics_summary:
        parts.append(f"\nAuthor metrics:\n{author_metrics_summary}")
    return "\n".join(parts)


async def run_author_voice_agent(
    *,
    chapter_prose: str,
    voice_metrics: VoiceMetrics,
    author_metrics: AuthorMetrics,
    novel_title: str,
    novel_genre: str,
    novel_id: UUID,
    language: str,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig,
    composed_prompt: ComposedPrompt,
    api_key: str | None = None,
    base_url: str | None = None,
    run_limit_resolver: DefaultRunLimitResolver | None = None,
) -> AuthorVoiceOutput:
    """Format runtime content and run one :class:`AuthorVoiceAgent` call.

    Args:
        chapter_prose: The author's full chapter prose (narration + dialogue
            together). Truncated to a representative excerpt for the model
            (the metrics are already computed over the full prose).
        voice_metrics: Voice-generic deterministic metrics (from
            :meth:`VoiceMetricsAnalyzer.analyze_text`).
        author_metrics: Author-specific prose-level deterministic metrics
            (from :class:`AuthorMetricsAnalyzer`).
        novel_title: Novel title for agent deps.
        novel_genre: Novel genre for agent deps.
        novel_id: Novel id (for error logging).
        language: Writing language code.
        model_registry: Model registry used to resolve the configured model.
        model_config: Resolved model configuration.
        composed_prompt: The composed system + user prompt (Mode 1).
        api_key: Optional per-user provider API key override (model-routing
            cascade) — injected into ``ModelRegistry.prepare``.
        base_url: Optional per-user provider base URL override.

    Returns:
        The agent output (descriptive-only — binding boundary enforced at the
        :class:`AuthorVoiceOutput` type level).
    """
    prose_excerpt = _truncate_prose(chapter_prose)
    voice_metrics_summary = format_voice_metrics_summary(voice_metrics)
    author_metrics_summary = format_author_metrics_summary(author_metrics)
    run_prompt = build_author_voice_run_prompt(
        prose_excerpt, voice_metrics_summary, author_metrics_summary
    )

    # Single assembly point (Task 6a — Task 4/5 pattern): model + intent-aware
    # runtime settings + usage limits as one coherent triple, so the thinking
    # policy actually reaches this call.
    resolved = (run_limit_resolver or DefaultRunLimitResolver()).resolve(
        config=model_config, budget=None, invocation_id=uuid4()
    )
    prepared = await model_registry.prepare(
        model_config,
        intent=LLMIntent.VOICE,
        usage_limits=resolved.usage_limits,
        api_key=api_key,
        base_url=base_url,
    )

    from narrare_core.agents.author_voice_agent import AuthorVoiceAgent
    from narrare_core.agents.author_voice_types import AuthorVoiceDeps

    deps = AuthorVoiceDeps(
        chapter_prose=prose_excerpt,
        voice_metrics_summary=voice_metrics_summary,
        author_metrics_summary=author_metrics_summary,
        project_title=novel_title,
        genre=novel_genre,
        writing_language=language,
    )
    try:
        agent = AuthorVoiceAgent(model=prepared.model, system_prompt=composed_prompt.system)
        output = await agent.run(
            prompt=composed_prompt.user or run_prompt,
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )
    except Exception as exc:
        logger.error(
            "author_voice_agent_failed",
            novel_id=str(novel_id),
            error=str(exc),
            exc_info=True,
        )
        raise
    return output
