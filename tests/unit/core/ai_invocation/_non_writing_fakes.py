"""Shared test helpers for non-writing invocation adapter tests.

All factory functions return fresh instances for test isolation.
Migrated from test_non_writing_adapter.py during RULE-04 modularization.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration
from narrare_core.ai_invocation.models import PromptInvocationContext, ValidationResult
from narrare_core.ai_invocation.pipeline import FinalizedInvocation, PreparedInvocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.prompts.context import PromptContext


def invocation_ctx(**overrides: object) -> PromptInvocationContext:
    defaults: dict[str, object] = {
        "feature_id": "analysis/beta_read",
        "intent": LLMIntent.SUMMARIZE,
        "mode": "beta_read",
        "language": "en",
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def prompt_ctx(**overrides: object) -> PromptContext:
    defaults: dict[str, object] = {
        "language": "en",
        "mode": "beta_read",
        "project_title": "Test Novel",
    }
    defaults.update(overrides)
    return PromptContext(**defaults)  # type: ignore[call-arg]


def composed_prompt() -> ComposedPrompt:
    return ComposedPrompt(system="real system prompt", user="real user prompt")


def manual_declaration(**overrides: object) -> ManualInjectionDeclaration:
    defaults: dict[str, object] = {
        "reason": "KBConsistencyAnalyzer composes prompts internally from deps.",
        "variables": ("entity_summaries", "template_structures"),
        "injection_mechanism": "agent_deps",
    }
    defaults.update(overrides)
    return ManualInjectionDeclaration(**defaults)  # type: ignore[arg-type]


def mock_composer(return_value: ComposedPrompt | None = None) -> MagicMock:
    composer = MagicMock(spec=["build"])
    composer.build = AsyncMock(return_value=return_value or composed_prompt())
    return composer


def passing_prepared(
    *,
    enriched_inputs: dict[str, str] | None = None,
    budget: object | None = None,
) -> PreparedInvocation:
    ctx = invocation_ctx()
    if enriched_inputs:
        ctx = ctx.model_copy(update={"dynamic_inputs": enriched_inputs})
    return PreparedInvocation(
        context=ctx,
        budget=budget,  # type: ignore[arg-type]
        validation=ValidationResult(status=ValidationStatus.PASS),
        enrichment_result=None,
    )


def passing_finalized() -> FinalizedInvocation:
    return FinalizedInvocation(
        validation=ValidationResult(status=ValidationStatus.PASS),
        evidence_recorded=True,
    )


def mock_pipeline_pass(
    *,
    prepared: PreparedInvocation | None = None,
    finalized: FinalizedInvocation | None = None,
) -> MagicMock:
    mock = MagicMock(spec=["prepare", "finalize"])
    mock.prepare = AsyncMock(return_value=prepared or passing_prepared())
    mock.finalize = AsyncMock(return_value=finalized or passing_finalized())
    return mock
