"""Agent execution helpers for BetaReaderService.

Extracted from beta_reader_service.py for RULE-04 compliance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.beta_reader_mapper import build_deepdive_prompt, build_user_prompt
from narrare.analysis.errors import AnalysisError
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from narrare_core.agents.beta_reader_agent import BetaReaderAgent
    from narrare_core.agents.beta_reader_types import (
        BetaReaderDeps,
        BetaReaderPhase1Output,
        BetaReaderPhase2Output,
    )
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


async def compose_analysis_prompt(
    composer: PromptComposer,
    language: str,
    mode: str,
) -> ComposedPrompt:
    """Compose system prompt via PromptComposer."""
    ctx = PromptContext(language=language, mode=mode, project_title="")
    try:
        return await composer.build(LLMIntent.BETA_READ, ctx)
    except Exception as exc:
        logger.error("prompt_composition_failed", mode=mode, error=str(exc))
        raise AnalysisError("Failed to compose analysis prompt") from exc


async def run_agent_phase1(
    agent: BetaReaderAgent,
    deps: BetaReaderDeps,
) -> BetaReaderPhase1Output:
    """Run Phase 1 agent with error handling."""
    try:
        return await agent.run_phase1(build_user_prompt(deps), deps=deps)
    except AnalysisError:
        raise
    except Exception as exc:
        logger.error("agent_execution_failed", error=str(exc))
        raise AnalysisError("Analysis execution failed") from exc


async def run_agent_phase2(
    agent: BetaReaderAgent,
    deps: BetaReaderDeps,
    model: object,
) -> BetaReaderPhase2Output:
    """Run Phase 2 agent with error handling."""
    try:
        return await agent.run_phase2(build_deepdive_prompt(deps), deps=deps, model=model)
    except AnalysisError:
        raise
    except Exception as exc:
        logger.error("agent_execution_failed_deep_dive", error=str(exc))
        raise AnalysisError("Deep-dive execution failed") from exc
