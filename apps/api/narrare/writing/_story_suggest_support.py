"""Story-suggest prompt/invocation assembly (RULE-04 split, ADR-086 L34).

Extracted from ``StorySuggestService.suggest`` so the service stays under
the 300-line limit when the lazy model-resolution seam
(``ensure_resolved`` + graceful entry-point policy + the pre-stream
``validate_suggest`` seam) was added for ADR-086 L34. Pure Mode 1
assembly of the story-suggest invocation:

- Prompt resolution is Mode 1 (composer-driven) per ADR-054 D1/D7/D8:
  the governed ``_bundled/writing/{locale}/story_suggest/system.md``
  template carries the task framing and project metadata variables. No
  inline prompt strings (RULE-02 / RULE-02a).
- The ``chapter_outline`` slot is fed from the injected
  ``OutlineRepository`` + ``ScenePlanRepository`` when a chapter is
  targeted (§7; PLAN-001 T15 renders scene blocks — stage + numbered
  scenes + notes); empty otherwise (legitimate RULE-11 — story-suggest
  is a project-level tool and a chapter need not be selected;
  allowlisted confirmed-optional var).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.writing._outline_render import render_chapter_outline
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.novels.models import Novel
    from narrare.planning.contracts import (
        OutlineRepositoryProtocol,
        ScenePlanRepositoryProtocol,
    )
    from narrare.planning.models import ScenePlan
    from narrare.writing.schemas_story_suggest import StorySuggestRequest
    from narrare_core.agents.story_suggest_types import StorySuggestOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer


async def compose_story_suggest_prompt(
    *,
    composer: PromptComposer,
    outline_repo: OutlineRepositoryProtocol | None,
    invocation_pipeline: InvocationPipeline | None,
    novel: Novel,
    novel_id: UUID,
    user_id: UUID,
    request: StorySuggestRequest,
    language: str,
    scene_repo: ScenePlanRepositoryProtocol | None = None,
) -> ComposedPrompt:
    """Assemble the Mode 1 story-suggest invocation and return the prompt.

    Builds the project-metadata ``PromptContext``, wires the targeted
    chapter's outline + scene plans into the ``chapter_outline`` slot,
    and resolves the governed system prompt via ``compose_invocation``
    (RULE-02 / ADR-054 D1).

    Args:
        composer: PromptComposer for the governed template (RULE-02b).
        outline_repo: Outline repository backing the ``chapter_outline``
            slot (unused when no chapter is targeted).
        invocation_pipeline: Optional pipeline for invocation evidence.
        novel: The novel (title/genre/structure metadata).
        novel_id: Target novel UUID (invocation-context project id).
        user_id: Authenticated user identifier.
        request: Story suggest request (optional ``chapter_id`` and
            ``author_instructions``).
        language: Resolved writing language.
        scene_repo: Scene-plan repository for the chapter's scene blocks
            (spec §7). ``None`` degrades gracefully (RULE-11): the slot
            carries stage + notes without scene blocks.

    Returns:
        The composed prompt (system + user channels).

    Raises:
        ConfigurationError: If composition produced no system prompt
            (Mode 1 invariant) or composition itself fails (RULE-11 —
            propagated, never swallowed).
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    ctx = PromptContext(
        language=language,
        writing_language=language,
        project_title=novel.title,
        genre=novel.genre or "",
        story_structure=novel.story_structure or "",
        mode="story_suggest",
        author_instructions=request.author_instructions or "",
        extra={
            "chapter_id": str(request.chapter_id) if request.chapter_id else "",
            # Declared explicitly so template substitution always
            # succeeds; populated below when a chapter is targeted.
            # Empty when no chapter_id is set (legitimate RULE-11 —
            # story-suggest is a project-level tool and a chapter need
            # not be selected; allowlisted as a confirmed-optional var).
            "chapter_outline": "",
        },
    )

    # Wire the chapter outline (stage + scene blocks + notes) when a
    # chapter is targeted (§7, PLAN-001 T15). Skipped when there is no
    # chapter_id or no outline repo — the slot stays empty (RULE-11,
    # allowlisted). A missing scene repo degrades to stage + notes.
    if request.chapter_id is not None and outline_repo is not None:
        outline = await outline_repo.get_by_chapter_id(request.chapter_id)
        if outline is not None:
            scenes: Sequence[ScenePlan] = []
            if scene_repo is not None:
                scenes = await scene_repo.list_by_chapter(request.chapter_id)
            ctx.extra["chapter_outline"] = render_chapter_outline(outline, scenes)

    invocation_context = build_invocation_context(
        feature_id="writing_story_suggest",
        intent=LLMIntent.SUGGEST,
        project_id=novel_id,
        user_id=user_id,
        language=language,
    )
    invocation = await compose_invocation(
        invocation_pipeline=invocation_pipeline,
        invocation_context=invocation_context,
        composer=composer,
        prompt_context=ctx,
        intent=LLMIntent.SUGGEST,
    )
    composed_prompt = invocation.composed_prompt
    # Mode 1 guarantees composed_prompt is set; the guard documents the
    # invariant and satisfies the type-checker (RULE-11: no silent None).
    if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
        raise ConfigurationError(
            "Prompt composition produced no system prompt for story suggestions.",
            code="COMPOSITION_EMPTY",
        )
    return composed_prompt


async def run_story_suggest_agent(
    *,
    registry: ModelRegistry,
    config: ResolvedModelConfig,
    run_limit_resolver: DefaultRunLimitResolver,
    composed_prompt: ComposedPrompt,
    novel: Novel,
    request: StorySuggestRequest,
    language: str,
) -> StorySuggestOutput:
    """Resolve the prepared triple and run the story-suggest agent.

    Task 6c single assembly point: the coherent
    ``(model, model_settings, usage_limits)`` triple from
    ``ModelRegistry.prepare``. No credential overrides exist on this
    service (they default to None). The composed system prompt reaches
    the agent CONSTRUCTOR (pydantic-ai binds ``system_prompt`` at
    construction); the project data flows as the run prompt (runtime
    data, RULE-02a category 3) when the template has no
    "## First Message".

    Raises:
        ConfigurationError: Propagated from prompt assembly/prepare
            (RULE-11 — never swallowed).
    """
    from uuid import uuid4

    from narrare_core.agents.story_suggest_agent import StorySuggestAgent
    from narrare_core.agents.story_suggest_types import StorySuggestDeps
    from narrare_core.llm.intents import LLMIntent

    resolved = run_limit_resolver.resolve(config=config, budget=None, invocation_id=uuid4())
    prepared = await registry.prepare(
        config, intent=LLMIntent.SUGGEST, usage_limits=resolved.usage_limits
    )

    # Build agent dependencies — minimal runtime data per
    # StorySuggestDeps (project-level fields only).
    deps = StorySuggestDeps(
        project_title=novel.title,
        genre=novel.genre or "",
        writing_language=language,
    )

    agent = StorySuggestAgent(model=prepared.model, system_prompt=composed_prompt.system)
    return await agent.run(
        prompt=composed_prompt.user
        or (
            f"Project: {novel.title}\n"
            f"Genre: {novel.genre or ''}\n"
            f"Story structure: {novel.story_structure or ''}\n"
            f"Author instructions: {request.author_instructions or ''}"
        ),
        deps=deps,
        model_settings=prepared.model_settings,
        usage_limits=prepared.usage_limits,
    )
