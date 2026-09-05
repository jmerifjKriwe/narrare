"""Dialogue-coach agent invocation helper (Mode 1 + one LLM call).

Extracted from ``service.py`` for RULE-04 compliance (service < 300 LOC).
Owns the single responsibility of running the ``DialogueCoachAgent`` with
the resolved prompt.

Plan-Bug #21 resolution: the original plan raised ``NotFoundError`` when
``model_config is None``. That is the wrong layer for the check — the
unit tests inject a ``FakeModelRegistry`` whose ``prepare()`` ignores
the config (and the test harness passes ``model_config=None``), while
production wiring (the DI factory) always supplies a real
``ResolvedModelConfig`` resolved through the per-user model-routing
cascade (user-scoped LLM credentials), with ``api_key``/``base_url``
threaded into ``registry.prepare()`` at the actual resolution point.
The check therefore blocked the tests without protecting production.
Removed here (Option A): the registry is the right validation layer, and
adding ``model_config`` null-checks inside the agent runner is
defensive-but-wrong-layer. Mirrors the ``voice_check_agent_runner``
precedent, which performs no such check.

See:
    ADR-069 (Dialogue Coach vertical),
    RULE-04 (Modularise, never compress).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

import structlog

from narrare.ai_assist._runtime_content import build_run_prompt
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import DefaultRunLimitResolver

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.agents.dialogue_coach_types import DialogueCoachOutput
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import ResolvedRunLimits
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


async def run_dialogue_coach_agent(
    *,
    selection_text: str,
    mode: str,
    characters: list[str],
    project_title: str,
    genre: str,
    language: str,
    voice_profiles_text: str,
    chapter_id: UUID,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig | None,
    api_key: str | None = None,
    base_url: str | None = None,
    run_limit_resolver: DefaultRunLimitResolver | None = None,
    composed_prompt: ComposedPrompt,
) -> DialogueCoachOutput:
    """Build Deps + run one DialogueCoachAgent call.

    Args:
        selection_text: The dialogue passage (category-3 runtime content).
        mode: "analyze" or "improve".
        characters: Canonical speaker roster.
        project_title: Novel title.
        genre: Novel genre.
        language: Writing language code.
        voice_profiles_text: Descriptive voice profiles text (ADR-055/057
            boundary — never voice_metrics).
        chapter_id: Chapter id (for logging).
        model_registry: Model registry.
        model_config: Resolved model config. ``None`` only in the unit-test
            harness (the fake registry ignores it); production always
            supplies a real config (see module docstring, Plan-Bug #21).
        api_key: Resolved per-user credential — overrides the provider env
            var when provided. ``None`` only in the unit-test harness.
        base_url: Resolved base-URL override for OpenAI-compatible
            providers. ``None`` uses the provider default endpoint.
        composed_prompt: The composed system + user prompt (Mode 1).

    Returns:
        The DialogueCoachOutput.
    """
    from narrare_core.agents.dialogue_coach_agent import DialogueCoachAgent
    from narrare_core.agents.dialogue_coach_types import DialogueCoachDeps

    # model_config is None only in the unit-test harness (the fake registry
    # ignores it). Production wiring always supplies a real config via the DI
    # factory (Plan-Bug #21). cast() narrows without a type-ignore (RULE-23)
    # and is runtime-free; the fake registry's prepare accepts Any.
    # api_key/base_url carry the resolved per-user credentials (per-user
    # model-routing cascade) into the single assembly point (Task 6d —
    # Task 4/5 pattern): model + intent-aware runtime settings + usage
    # limits as one coherent triple. The ADR-045 run-limit resolver applies
    # the output cap; a None config (harness-only) skips resolution.
    resolved: ResolvedRunLimits | None = None
    if model_config is not None:
        resolved = (run_limit_resolver or DefaultRunLimitResolver()).resolve(
            config=model_config, budget=None, invocation_id=uuid4()
        )
    prepared = await model_registry.prepare(
        cast("ResolvedModelConfig", model_config),
        intent=LLMIntent.DIALOGUE_COACH,
        usage_limits=resolved.usage_limits if resolved else None,
        api_key=api_key,
        base_url=base_url,
    )
    deps = DialogueCoachDeps(
        text_to_analyze=selection_text,
        mode=mode,
        characters=characters,
        project_title=project_title,
        genre=genre,
        writing_language=language,
        voice_profiles_text=voice_profiles_text,
    )
    agent = DialogueCoachAgent(model=prepared.model, system_prompt=composed_prompt.system)
    try:
        output = await agent.run(
            prompt=composed_prompt.user
            or build_run_prompt(selection_text=selection_text, mode=mode, characters=characters),
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )
    except Exception as exc:
        logger.error(
            "dialogue_coach_agent_failed",
            chapter_id=str(chapter_id),
            error=str(exc),
            exc_info=True,
        )
        raise
    return output
