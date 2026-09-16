"""Timeline analysis prompt-context assembly (RULE-04 split, ADR-086 L22).

Extracted from ``TimelineAnalysisService.generate_timeline`` so the
service stays under the 300-line limit when the lazy model-resolution
seam (``ensure_resolved`` + graceful entry-point policy) was added for
ADR-086 L22. Pure assembly: fetches the canonical KB context, renders
chapter summaries and confirmed events, and returns the ``PromptContext``
the ``PromptComposer`` consumes (RULE-02 — no inline prompt strings).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.models import Chapter
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.novels.models import Novel
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare_core.prompts.context import PromptContext


async def build_prompt_context(
    novel: Novel,
    chapters: list[Chapter],
    language: str,
    novel_id: uuid.UUID,
    event_repo: TimelineEventRepository | None,
    kb_context_provider: KBContextProviderProtocol | None,
) -> PromptContext:
    """Assemble the timeline ``PromptContext`` (ADR-049 D9, Mode 1).

    Compact chapter-summary context fills ``{{chapter_summaries}}`` plus
    the agent run prompt; the canonical KB-context provider (ADR-067)
    supplies ``kb_characters``/``kb_locations``/``kb_factions``/
    ``kb_relationships``, rendered through the ADR-050 envelope with
    provenance (FIND-017), degrading to empty strings when no provider is
    wired or the KB is empty (RULE-11).

    Args:
        novel: The novel (title/genre metadata).
        chapters: The novel's chapters (summaries rendered compactly).
        language: Resolved writing language.
        novel_id: Target novel UUID (event rendering + KB fetch).
        event_repo: For confirmed events (``entity_events``); empty-but-
            valid when ``None`` or no events exist (RULE-11).
        kb_context_provider: Canonical KB-context provider (ADR-067).

    Returns:
        The composed ``PromptContext`` (mode="timeline").
    """
    # Runtime imports kept local to match the consuming service module's
    # existing import convention and avoid module-load circular-import
    # risk.
    from narrare.planning._event_render import render_confirmed_events
    from narrare.planning._timeline_chapter_context import format_chapter_context
    from narrare_core.context._render_options import RenderOptions
    from narrare_core.prompts.context import PromptContext

    # Compact chapter-summary context — runtime data (RULE-02a category 3)
    # that fills ``{{chapter_summaries}}`` + the agent run prompt.
    chapter_context = format_chapter_context(chapters)

    # Canonical KB context (ADR-067): characters/locations/factions/
    # relationships are fetched+rendered through the reusable provider
    # (the ADR-050 envelope, with provenance annotated so planning gets the
    # same honest rendering as writing — FIND-017). Degrades to empty
    # strings when no provider is wired or the KB is empty (RULE-11).
    if kb_context_provider is None:
        from narrare.kb.context_contracts import KBContextBundle

        kb_bundle = KBContextBundle.empty(RenderOptions(annotate_provenance=True))
    else:
        kb_bundle = await kb_context_provider.fetch_context(
            novel_id,
            entity_types=["character", "location", "faction"],
            options=RenderOptions(annotate_provenance=True),
        )
    kb_vars = kb_bundle.to_prompt_variables()

    # Resolve the governed timeline system prompt via PromptComposer
    # (RULE-02 / ADR-049 D9). The template
    # ``_bundled/planning/en/timeline/system.md`` carries the task framing,
    # project metadata, and KB context variables.
    #
    # KB context variables (kb_characters, kb_locations, kb_factions,
    # kb_relationships) flow from the provider above (ADR-067).
    # ``entity_events`` is wired from the already-injected event_repo
    # (confirmed events rendered compactly; §7 closed). Corrects the
    # prior stale "ADR-049 D8 notes" comment (D8 governs the timeline
    # template, not this slot).
    # ``culture_guidelines`` is NOT set here: it is unconditionally
    # auto-injected by the PromptComposer (resolved from ``name_style``
    # or empty string — see composer.py).
    return PromptContext(
        language=language,
        writing_language=language,
        project_title=novel.title,
        genre=novel.genre or "",
        mode="timeline",
        extra={
            "chapter_summaries": chapter_context,
            # Confirmed entity events, rendered from the event_repo;
            # empty-but-valid when none exist or no repo is wired (RULE-11).
            "entity_events": await render_confirmed_events(event_repo, novel_id),
            # kb_* spread from the provider — non-empty when the KB has
            # those entities, empty on degradation (RULE-11). Spread (not
            # a literal) so the §7 stub guard treats the slots as fed.
            **kb_vars,
        },
    )
