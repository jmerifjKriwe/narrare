"""Invocation assembly for the Series Voice profile pipeline (ADR-086 L28).

Extracted from ``series_voice_service.py`` (RULE-04: the ADR-086
``ensure_resolved`` addition crossed the 300-line service limit —
modularize, don't compress). One responsibility: run ONE series-voice
profiling invocation over a novel's chapter prose and return the
assembled :class:`AuthorVoiceProfile` — no ownership checks, no
persistence (both stay in the service).

Reuses the EXISTING ADR-074 author-voice pipeline in the SAME order the
service called it inline (timing-only migration: WHAT unchanged):

    :func:`resolve_author_voice_prompt`   — Mode-1 governed ``author_voice``
        system prompt via :class:`PromptComposer` (RULE-02/02b).
    :func:`run_author_voice_agent`        — one ``AuthorVoiceAgent`` LLM call,
        fed the resolved model triple (config + credentials) from the
        lazy routing cascade (ADR-086).
    :func:`assemble_author_voice_profile` — descriptive + metric groups.

The chapter prose + precomputed metrics flow as runtime content in the
agent run prompt (RULE-02a category 3); no inline feature prompt is
assembled here (RULE-02).

See:
    ADR-086 L28 — the lazy-resolution slice that extracted this module.
    ADR-074 — Author Voice Storage Contract (the pipeline reused).
    ADR-078 — Series Voice Hierarchy (Delta model).
    RULE-01b/02/04/06.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.analysis.author_voice_agent_runner import run_author_voice_agent
from narrare.analysis.author_voice_profile_assembler import assemble_author_voice_profile
from narrare.analysis.author_voice_prompt import resolve_author_voice_prompt

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.novels.models import Novel
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.profiles.author_voice import AuthorVoiceProfile
    from narrare_core.prompts.composer import PromptComposer


async def run_series_voice_invocation(
    *,
    registry: ModelRegistry,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    resolved_model: ResolvedModel,
    novel: Novel,
    chapters: list[Chapter],
    language: str,
    novel_id: UUID,
    user_id: UUID,
) -> AuthorVoiceProfile:
    """Run one series-voice profiling invocation over a novel's prose.

    Metrics → governed prompt → one agent call → profile assembly (the
    reused ADR-074 pipeline steps 4-8, verbatim order). The resolved
    model triple arrives pre-resolved by the caller (ADR-086 first-use
    semantics — this module never touches the routing cascade).

    Args:
        registry: Model registry for the AuthorVoiceAgent.
        composer: PromptComposer for the governed author_voice prompt.
        invocation_pipeline: Optional InvocationPipeline for evidence.
        resolved_model: The lazily resolved routing triple (config +
            credentials) — flows into ``ModelRegistry.prepare`` verbatim.
        novel: The member novel (title/genre read for the prompt context).
        chapters: The novel's chapters (``list_by_novel`` order); prose
            is read from ``Chapter.content``.
        language: Writing language code (novel → series fallback chain).
        novel_id: The novel id (invocation context project_id).
        user_id: The requesting user id (invocation context user_id).

    Returns:
        The assembled :class:`AuthorVoiceProfile` (descriptive + metrics).
    """
    # 1. Compute deterministic metrics over the full prose (narration +
    #    dialogue together — the author-voice input shape, ADR-074). The
    #    analyzers are deterministic Core code; the LLM seam is the agent
    #    (step 3), so no override hook is needed (unlike the streaming
    #    AuthorVoiceService, which exposes one for its tests).
    from narrare_core.analysis.author_metrics import AuthorMetricsAnalyzer
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

    chapter_prose_list = [(c.content or "") for c in chapters]
    combined_prose = "\n\n".join(chapter_prose_list)
    voice_metrics = VoiceMetricsAnalyzer(language=language).analyze_text(chapter_prose_list)
    author_metrics = AuthorMetricsAnalyzer().analyze(chapter_prose_list)

    # 2. Resolve the governed author_voice system prompt (RULE-02 / ADR-054
    #    Mode 1). Reused verbatim from the novel-level pipeline.
    composed_prompt = await resolve_author_voice_prompt(
        composer,
        invocation_pipeline,
        novel=novel,
        language=language,
        novel_id=novel_id,
        user_id=user_id,
    )

    # 3. Run the existing AuthorVoiceAgent (one LLM call) with the
    #    coherently prepared model triple.
    output = await run_author_voice_agent(
        chapter_prose=combined_prose,
        voice_metrics=voice_metrics,
        author_metrics=author_metrics,
        novel_title=novel.title,
        novel_genre=novel.genre or "",
        novel_id=novel_id,
        language=language,
        model_registry=registry,
        model_config=resolved_model.config,
        composed_prompt=composed_prompt,
        api_key=resolved_model.api_key,
        base_url=resolved_model.base_url,
    )

    # 4. Assemble the profile (descriptive + metric groups, ADR-074).
    return assemble_author_voice_profile(
        descriptive=output,
        voice_metrics=voice_metrics,
        author_metrics=author_metrics,
    )
