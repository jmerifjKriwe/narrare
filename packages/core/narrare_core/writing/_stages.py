"""Pipeline stage helpers — the named stages of :meth:`WritingPipeline.generate`.

Extracts the Stage-1 (voice-profile resolution) and Stage-2 (context assembly)
helpers out of :meth:`WritingPipeline.generate` (RULE-04: modularize, not
minify; RULE-06: one responsibility per module). This mirrors the existing
Stage-4 extraction :mod:`narrare_core.writing._mode_dispatch`: each stage is a
module-level function called directly from ``generate()``, taking the owning
:class:`WritingPipeline` as its first argument.

Stage contracts (AUFG-01-08):

    1. :func:`resolve_voice_profile_consumer`
       in:  the owning WritingPipeline (its voice-profile consumer factory)
            and the request's KB entities (``list[KBEntity] | None``).
       out: ``VoiceProfileConsumer | None``  (``None`` when no factory/entities).

    2. :func:`assemble_writing_context`
       in:  the owning WritingPipeline (its context assembler), the request,
            the call-level context inputs and the Stage-1 consumer.
       out: ``WritingContext``  (fully tiered; NO prompt built here — RULE-02).

``pipeline`` is passed (rather than the individual collaborators) so the stage
helpers mirror the established intra-package coupling of
:func:`narrare_core.writing._mode_dispatch.stream_for_mode`, which already
receives the pipeline instance to reach its private helpers/deps. Reached from
this sibling module, the private-attribute accesses are bound to locals under
coded ``reportPrivateUsage`` suppressions (RULE-23).

This module is internal to the writing subsystem — not part of the public API.

See:
    AUFG-01-08, CONSTRAINTS.md RULE-02 / RULE-04 / RULE-06 / RULE-23.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.profiles.contracts import VoiceProfileConsumer
    from narrare_core.writing.context_models import KBEntity, RecentChapter
    from narrare_core.writing.models import GenerationRequest, WritingContext
    from narrare_core.writing.pipeline import WritingPipeline


def resolve_voice_profile_consumer(
    pipeline: WritingPipeline,
    kb_entities: list[KBEntity] | None,
) -> VoiceProfileConsumer | None:
    """Stage 1 — voice-profile consumer resolution.

    Builds a :class:`VoiceProfileConsumer` from the supplied KB entities
    when (a) a consumer factory is wired and (b) KB entities are present.
    Otherwise returns ``None`` (voice profiling disabled for this request).

    Args:
        pipeline: Owning WritingPipeline (provides the consumer factory).
        kb_entities: KB entities available for the request, or ``None``.

    Returns:
        A VoiceProfileConsumer, or ``None`` when profiling is disabled.
    """
    factory = pipeline._voice_profile_consumer_factory  # pyright: ignore[reportPrivateUsage]
    if factory is not None and kb_entities:
        return factory(kb_entities)
    return None


async def assemble_writing_context(
    pipeline: WritingPipeline,
    request: GenerationRequest,
    *,
    voice_profile_consumer: VoiceProfileConsumer | None,
    chapter_content: str,
    chapter_frontmatter: str,
    chapter_outline: str,
    recent_chapters: list[RecentChapter] | None,
    kb_entities: list[KBEntity] | None,
    entity_connections: dict[str, set[str]] | None,
    kb_relationships: str,
    project_title: str,
    genre: str,
    user_preferences: str,
    avoidance_patterns: str,
) -> WritingContext:
    """Stage 2 — context assembly.

    Bundles the request- and call-level context inputs and delegates to the
    pipeline's :class:`WritingContextAssembler` to produce a fully assembled
    :class:`WritingContext` (KB tiering, voice profiles, recent chapters,
    project metadata). No prompt is constructed here (RULE-02).

    Args:
        pipeline: Owning WritingPipeline (provides the context assembler).
        request: The generation request (source of project_id, language,
            tone, word_target and the stringified mode).
        voice_profile_consumer: Optional consumer from Stage 1.
        chapter_content: Existing chapter text for continuation.
        chapter_frontmatter: Chapter metadata / frontmatter.
        chapter_outline: Chapter outline or structure notes.
        recent_chapters: Recent chapters for context.
        kb_entities: Knowledge base entities for reference.
        entity_connections: Adjacency map of entity IDs for classification.
        kb_relationships: Pre-formatted relationship text (FIND-009).
        project_title: Title of the project / novel.
        genre: Genre of the writing project.
        user_preferences: User's writing preference string.
        avoidance_patterns: Patterns the user wants to avoid.

    Returns:
        The assembled WritingContext ready for prompt construction.
    """
    assembler = pipeline._context_assembler  # pyright: ignore[reportPrivateUsage]
    return await assembler.assemble(
        chapter_content=chapter_content,
        chapter_frontmatter=chapter_frontmatter,
        chapter_outline=chapter_outline,
        project_id=request.project_id,
        recent_chapters=recent_chapters,
        kb_entities=kb_entities,
        entity_connections=entity_connections,
        kb_relationships=kb_relationships,
        project_title=project_title,
        genre=genre,
        language=request.writing_language,
        writing_language=request.writing_language,
        tone=request.tone,
        word_target=request.word_target,
        user_preferences=user_preferences,
        avoidance_patterns=avoidance_patterns,
        mode=str(request.mode),
        voice_profile_consumer=voice_profile_consumer,
    )
