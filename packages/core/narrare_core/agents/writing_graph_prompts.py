"""Prompt building helpers and shared utilities for WritingGraph steps.

Extracted from writing_graph.py to respect the 200-line limit (RULE-04).
Contains:
- Prompt building functions for each graph step
- Shared helpers (save_state, get_model)

KB context assembly (``_assemble_writing_context``) and prompt enrichment
(``_enrich_prompt_context_with_kb``) live in ``writing_graph_kb_context.py``
(RULE-04 extraction) and are re-imported here for the graph steps and the
existing import surface.

See CONSTRAINTS.md RULE-02 (all prompts from PromptComposer).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from narrare_core.agents.writing_graph_kb_context import (
    assemble_writing_context,
    enrich_prompt_context_with_kb,
)
from narrare_core.agents.writing_graph_types import Approved, NeedsRevision
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import ConfigurationError
from narrare_core.writing._helpers import context_bullet, word_target_line
from narrare_core.writing.models import WritingContext

if TYPE_CHECKING:
    from pydantic_graph import StepContext

    from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer

# CR-AUFG-02-07 / ADR-046: The ``composer is None`` fallback paths were
# removed. ``PromptComposer`` is now a required dependency (RULE-11:
# fail-fast, never silently degrade to inline prompts).
_COMPOSER_MISSING_MSG = (
    "PromptComposer is required for writing graph production paths — "
    "WritingDeps.composer must be wired by the DI container."
)
_COMPOSER_MISSING_CODE = "writing_graph_missing_composer"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def save_state(ctx: StepContext[WritingState, WritingDeps, Any]) -> None:
    """Save state checkpoint if store is configured."""
    if ctx.deps.store is not None and ctx.deps.run_id:
        await ctx.deps.store.save(ctx.deps.run_id, ctx.state)


async def get_model(deps: WritingDeps) -> Any:
    """Resolve model from the registry."""
    return await deps.registry.get_model(
        deps.model_config,
        api_key=deps.api_key,
        base_url=deps.base_url,
    )


async def get_or_create_agent(
    deps: WritingDeps,
    agent_type: type,
    model: Any,
    system_prompt: str | None = None,
    **kwargs: Any,
) -> Any:
    """Get agent from AgentRegistry if available, else create directly.

    Provides backward compatibility: if agent_registry is None,
    falls back to direct instantiation.
    """
    if deps.agent_registry is not None:
        return await deps.agent_registry.get_or_create(
            agent_type,
            model,
            system_prompt=system_prompt,
            **kwargs,
        )
    return agent_type(model=model, system_prompt=system_prompt, **kwargs)


# ---------------------------------------------------------------------------
# Prompt context builder
# ---------------------------------------------------------------------------


def _base_context(deps: WritingDeps, state: WritingState) -> PromptContext:
    """Build base PromptContext with fields common to all steps."""
    ctx = PromptContext(
        language=deps.language,
        writing_language=deps.writing_language,
        genre=deps.genre,
        tone=deps.tone,
        # Genre-mirror supply (project_title follow-up): the title rides
        # the same deps rail as genre — API seam → pipeline context →
        # WritingDeps — carried plainly here because template-owned
        # labels (e.g. new_chapter's ``- Project: {{project_title}}``
        # line) render the raw value; only the review supplier wraps it
        # in a label-in-value bullet below.
        project_title=deps.project_title,
        chapter_title=state.outline[:100] if state.outline else "",
    )
    # Enable preference auto-injection via PromptComposer
    if deps.user_id:
        ctx.extra["user_id"] = deps.user_id
    if state.novel_id:
        ctx.extra["project_id"] = state.novel_id
    return ctx


async def get_outline_prompt(
    composer: PromptComposer,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the plan_outline step.

    Raises:
        ConfigurationError: If ``composer`` is ``None`` — a DI-wiring error.
            Per ADR-046 / RULE-11 this fails fast rather than silently
            degrading to an inline prompt.
    """
    if cast("Any", composer) is None:
        raise ConfigurationError(_COMPOSER_MISSING_MSG, code=_COMPOSER_MISSING_CODE)

    context = _base_context(deps, state)
    context.mode = "outline"
    # FO-10: the planning/outline template demands {{variant_count}} (route-
    # required, MODE_REQUIRED_VARS; no deps/state owner exists — the graph
    # plans a single outline, the template's documented default of 1) and
    # {{kb_characters}} / {{kb_locations}} (PLAN declares no optionals).
    # KB supply mirrors get_draft_prompt: graceful-None assembly + the
    # kb_context_extras SSOT so placeholders render instead of raising.
    writing_context = await assemble_writing_context(deps, state)
    context.extra["variant_count"] = 1
    if deps.chapter_content:
        context.existing_content = deps.chapter_content[:500]
    enrich_prompt_context_with_kb(context, writing_context or WritingContext())

    composed: ComposedPrompt = await composer.build(LLMIntent.PLAN, context)
    return (composed.system, composed.user)


async def get_draft_prompt(
    composer: PromptComposer,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the write_draft step.

    Assembles the WritingContext (graceful-None, RULE-11) and enriches
    the prompt with the full KB variable set so the new_chapter template's
    Knowledge Base section renders curated context instead of empty
    placeholders.

    Raises:
        ConfigurationError: If ``composer`` is ``None`` — a DI-wiring error.
    """
    if cast("Any", composer) is None:
        raise ConfigurationError(_COMPOSER_MISSING_MSG, code=_COMPOSER_MISSING_CODE)

    # Assemble KB context — graceful degradation on failure: when assembly
    # yields None the draft proceeds KB-blind (kb_* render empty).
    writing_context = await assemble_writing_context(deps, state)

    context = _base_context(deps, state)
    context.mode = "new_chapter"
    if state.outline:
        context.author_instructions = state.outline
    if deps.chapter_content:
        context.existing_content = deps.chapter_content
    # Slice-2 word_target migration (2026-09-13): the new_chapter template
    # renders its word target via {{word_target_line}} (label-in-value,
    # append-to-previous-line) — the static "Word target:" label line is
    # gone from the template, so an unset target no longer renders a
    # dangling label. The full line is supplied unconditionally (None → ""
    # inside the shared helper), preserving the FO-3 key-present convention
    # for a non-route-optional placeholder; the bare {{word_target}} extra
    # is no longer referenced by this route's template and is not supplied
    # here — no supplied-but-unrendered dead data. Key-level assignment
    # also preserves the _base_context user/project extras.
    context.extra["word_target_line"] = word_target_line(deps.word_target, label="Word target: ")
    # WRITE route-required variable (route_table.py) — the draft step owns
    # the outline and must supply it for the template's {{chapter_outline}}.
    context.extra["chapter_outline"] = state.outline

    # KB-blind fallback: when assembly yields None (no assembler wired,
    # missing ids, or assembly failure), an empty WritingContext still
    # supplies every kb_* key as "" so the template's KB placeholders render
    # empty instead of raising PromptVariableError (RULE-11 graceful) —
    # mirroring how the writing pipelines always carry kb_context_extras.
    kb_source = writing_context if writing_context is not None else WritingContext()
    enrich_prompt_context_with_kb(context, kb_source)

    composed: ComposedPrompt = await composer.build(LLMIntent.WRITE, context)
    return (composed.system, composed.user)


async def get_review_prompt(
    composer: PromptComposer,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str, WritingContext | None]:
    """Return (system_prompt, user_prompt, writing_context) for the review_draft step.

    Assembles WritingContext from the context_assembler when available
    and enriches the prompt with KB data for consistency checks.
    Returns the assembled context so the caller can pass it to ReviewDeps.

    Raises:
        ConfigurationError: If ``composer`` is ``None`` — a DI-wiring error.
    """
    if cast("Any", composer) is None:
        raise ConfigurationError(_COMPOSER_MISSING_MSG, code=_COMPOSER_MISSING_CODE)

    draft_text = state.draft or ""

    # Assemble KB context — graceful degradation on failure
    writing_context = await assemble_writing_context(deps, state)

    context = _base_context(deps, state)
    context.mode = "review"
    # FO-3 pattern (review twin): key-level assignment preserves the
    # _base_context user/project extras that the previous dict-reassignment
    # wiped, re-enabling preference auto-injection for the review step.
    # Item F: the analysis/en/review template renders the word-target line
    # via {{word_target_line}} (label-in-value, append-to-previous-line) —
    # supplying the full line, "" when no target is set, so the empty case
    # cannot leave a dangling "- Word target: " bullet (the bare
    # {{word_target}} extra is no longer referenced by this route's template
    # and is not supplied here — no supplied-but-unrendered dead data).
    # Slice 2 dedup: the shared writing._helpers.word_target_line SSOT
    # (the former private twin here was removed).
    context.extra["word_target_line"] = word_target_line(deps.word_target, label="- Word target: ")
    # Review-dangles fix (2026-09-13): the leading Context bullets are
    # label-in-value too — the supplier builds the full bullet ("" when
    # unset → the line renders away, no dangling "- Project: " / "- Genre: "
    # label). Genre comes from deps ("" by default). The title prefers
    # deps (genre mirror — populated from the owned novel where deps are
    # constructed) with the assembled WritingContext metadata tier as the
    # best-effort fallback (data-fetching assemblers, ws_context_assembler
    # precedent).
    context.project_title = context_bullet(
        deps.project_title or (writing_context.project_title if writing_context else ""),
        "- Project: ",
    )
    context.genre = context_bullet(deps.genre, "- Genre: ")

    # FO-8: the governed composer route for the analysis/en/review template
    # is ANALYSE + mode="review" — BETA_READ does not allow mode="review"
    # (PromptRouteNotConfiguredError at compose). KB-blind fallback mirrors
    # the draft/revise convention: ANALYSE declares no optional variables,
    # so an empty WritingContext supplies every kb_* key as "" instead of
    # raising PromptVariableError when assembly yields None (RULE-11).
    kb_source = writing_context if writing_context is not None else WritingContext()
    enrich_prompt_context_with_kb(context, kb_source)

    composed: ComposedPrompt = await composer.build(
        LLMIntent.ANALYSE,
        context,
        user_prompt=draft_text,
    )
    return (composed.system, composed.user, writing_context)


async def get_revise_prompt(
    composer: PromptComposer,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the revise_draft step.

    Assembles the WritingContext (graceful-None, RULE-11) and enriches
    the prompt with the full KB variable set. The REWRITE route renders
    the new_chapter template via its context-mode override, so the same
    route-family variables (kb_* set, chapter_outline) apply as on the
    draft path (commit ac55a094 — identical defect class).

    Raises:
        ConfigurationError: If ``composer`` is ``None`` — a DI-wiring error.
    """
    if cast("Any", composer) is None:
        raise ConfigurationError(_COMPOSER_MISSING_MSG, code=_COMPOSER_MISSING_CODE)

    # Assemble KB context — graceful degradation on failure: when assembly
    # yields None the revision proceeds KB-blind (kb_* render empty).
    writing_context = await assemble_writing_context(deps, state)

    revise_content = "Revise based on feedback: " + state.feedback + "\n\n" + state.draft

    context = _base_context(deps, state)
    context.mode = "new_chapter"
    context.author_instructions = state.feedback
    context.existing_content = state.draft
    # Slice-2 word_target migration: REWRITE renders the new_chapter
    # template via its context-mode override — supply the full
    # label-in-value line exactly like the draft path (None → "" inside
    # the shared helper; the bare {{word_target}} extra is no longer
    # referenced by the rendered template and is not supplied here).
    context.extra["word_target_line"] = word_target_line(deps.word_target, label="Word target: ")
    # new_chapter-template placeholder ({{chapter_outline}}) is not
    # route-optional on the REWRITE context-mode override — the revise
    # step owns the outline and must supply it, exactly like the draft.
    context.extra["chapter_outline"] = state.outline

    # KB-blind fallback: when assembly yields None (no assembler wired,
    # missing ids, or assembly failure), an empty WritingContext still
    # supplies every kb_* key as "" so the template's KB placeholders
    # render empty instead of raising PromptVariableError (RULE-11
    # graceful) — mirroring the draft path.
    kb_source = writing_context if writing_context is not None else WritingContext()
    enrich_prompt_context_with_kb(context, kb_source)

    composed: ComposedPrompt = await composer.build(
        LLMIntent.REWRITE,
        context,
        user_prompt=revise_content,
    )
    return (composed.system, composed.user)


async def get_summary_prompt(
    composer: PromptComposer,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the generate_summary step.

    Raises:
        ConfigurationError: If ``composer`` is ``None`` — a DI-wiring error.
    """
    if cast("Any", composer) is None:
        raise ConfigurationError(_COMPOSER_MISSING_MSG, code=_COMPOSER_MISSING_CODE)

    content = state.final or state.draft
    chapter_title = state.outline[:100] if state.outline else ""

    context = _base_context(deps, state)
    context.mode = "summarize"
    context.chapter_title = chapter_title

    composed: ComposedPrompt = await composer.build(
        LLMIntent.SUMMARIZE,
        context,
        user_prompt=content[:3000],
    )
    return (composed.system, composed.user)


# ---------------------------------------------------------------------------
# Edge wiring
# ---------------------------------------------------------------------------


def add_edges(
    g: Any,
    plan_outline: Any,
    write_draft: Any,
    review_draft: Any,
    revise_draft: Any,
    finalize: Any,
    generate_summary: Any,
) -> None:
    """Wire up all edges for the writing graph.

    Extracted from writing_graph.py to respect the 200-line limit (RULE-04).
    """
    from pydantic_graph import TypeExpression

    g.add(
        g.edge_from(g.start_node).to(plan_outline),
        g.edge_from(plan_outline).to(write_draft),
        g.edge_from(write_draft).to(review_draft),
        g.edge_from(review_draft).to(
            g.decision()
            .branch(g.match(TypeExpression[Approved]).label("approved").to(finalize))
            .branch(g.match(TypeExpression[NeedsRevision]).label("needs revision").to(revise_draft))
        ),
        g.edge_from(revise_draft).to(write_draft),
        g.edge_from(finalize).to(generate_summary),
        g.edge_from(generate_summary).to(g.end_node),  # pyright: ignore[reportArgumentType]
    )
