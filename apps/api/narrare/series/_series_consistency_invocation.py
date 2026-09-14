"""Invocation assembly for the series-consistency check (ADR-086 L26).

Moved from ``series_consistency_service.py`` for the RULE-04 300-line
limit the lazy ``ensure_resolved`` addition crossed: same behavior, only
the module home changed (the ``kb/_consistency_invocation.py`` L15
convention). One responsibility (RULE-06): resolve the governed
``series_consistency`` prompt (ADR-054 Mode 1), format the runtime
content (Canon + chapter prose, user channel — RULE-02a category 3),
resolve the ADR-045 run limits, prepare the coherent model triple via
the Task 6d single assembly point, and run the agent exactly once.

Pattern: PromptComposer (RULE-02) → Core Agent (RULE-01b) — no business
decisions here; gates, graceful degradation, and response mapping stay
in the service.

See:
    ADR-075 — Series Foundation (Canon KB scope).
    ADR-045 — run-limit enforcement at the ``agent.run`` boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.series.series_consistency_prompt import resolve_series_consistency_prompt
from narrare.series.series_consistency_runtime_content import (
    format_canon_entries,
    format_run_prompt,
)
from narrare_core.agents.series_consistency_types import (
    SeriesConsistencyDeps,
    SeriesConsistencyOutput,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from narrare_core.agents.series_consistency_agent import SeriesConsistencyAgent
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.kb.schemas.entry import SeriesKBEntry
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer


async def run_series_consistency_invocation(
    *,
    registry: ModelRegistry,
    agent_factory: Callable[..., SeriesConsistencyAgent],
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    run_limit_resolver: DefaultRunLimitResolver,
    resolved_model: ResolvedModel,
    novel_title: str,
    genre: str | None,
    language: str,
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
    canon_entries: list[SeriesKBEntry],
    chapter_texts: list[str],
) -> SeriesConsistencyOutput:
    """Compose, prepare, and run the series-consistency agent (1 LLM call).

    Returns the agent's :class:`SeriesConsistencyOutput`; response
    mapping and completion logging remain service concerns.
    """
    # 6. Resolve the governed series_consistency system prompt (RULE-02b)
    #    + format the runtime content (Canon + chapters, user channel).
    system_prompt = await resolve_series_consistency_prompt(
        composer,
        invocation_pipeline,
        novel_title=novel_title,
        genre=genre,
        language=language,
        novel_id=novel_id,
        user_id=user_id,
    )
    formatted_canon = format_canon_entries(canon_entries)

    # 7. Resolve model + instantiate agent (RULE-01b: agents-first).
    #    Single assembly point (Task 6d — Task 4/5 pattern): model +
    #    intent-aware runtime settings + usage limits as one coherent
    #    triple. The per-user provider credentials (model-routing
    #    cascade, resolved lazily by the service — ADR-086) are injected
    #    into the prepare call.
    resolved = run_limit_resolver.resolve(
        config=resolved_model.config, budget=None, invocation_id=uuid4()
    )
    prepared = await registry.prepare(
        resolved_model.config,
        intent=LLMIntent.ANALYSE,
        usage_limits=resolved.usage_limits,
        api_key=resolved_model.api_key,
        base_url=resolved_model.base_url,
    )
    agent = agent_factory(prepared.model, system_prompt)

    # 8. Run the agent. Canon entries + chapter texts flow as runtime
    #    content in the user-channel prompt (RULE-02a category 3);
    #    SeriesConsistencyDeps carries the same data for validators.
    deps = SeriesConsistencyDeps(
        canon_entries=formatted_canon,
        chapter_texts=chapter_texts,
        novel_title=novel_title,
    )
    return await agent.run(
        prompt=format_run_prompt(formatted_canon, chapter_texts),
        deps=deps,
        model_settings=prepared.model_settings,
        usage_limits=prepared.usage_limits,
    )
