"""Agent execution helpers for BetaReaderService.

Extracted from ``beta_reader_service.py`` to keep the service under
RULE-04's 300-line service file limit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.beta_reader_mapper import build_deepdive_prompt
from narrare.analysis.errors import AnalysisError

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from narrare_core.agents.beta_reader_agent import BetaReaderAgent
    from narrare_core.agents.beta_reader_types import (
        BetaReaderDeps,
        BetaReaderPhase1Output,
        BetaReaderPhase2Output,
    )

logger = structlog.get_logger(__name__)


async def run_phase1(
    agent: BetaReaderAgent,
    user_prompt: str,
    deps: BetaReaderDeps,
    *,
    model_settings: ModelSettings | None = None,
    usage_limits: UsageLimits | None = None,
) -> BetaReaderPhase1Output:
    """Run Phase 1 agent with error handling.

    ``model_settings``/``usage_limits`` come from the coherent
    ``ModelRegistry.prepare()`` triple and are forwarded to the
    underlying pydantic-ai run.
    """
    try:
        return await agent.run_phase1(
            user_prompt,
            deps=deps,
            model_settings=model_settings,
            usage_limits=usage_limits,
        )
    except AnalysisError:
        raise
    except Exception as exc:
        logger.error("agent_execution_failed", error=str(exc))
        raise AnalysisError("Analysis execution failed") from exc


async def run_phase2(
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
