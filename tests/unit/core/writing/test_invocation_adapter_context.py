"""Tests for user_id/project_id pass-through in _invocation_adapter.py.

Covers:
1. user_id and project_id flow through to auto-created context.
2. Explicit context overrides user_id/project_id parameters.
3. Defaults to None when nothing is provided.

See:
    INFRA-013, ADR-038, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import PromptInvocationContext, ValidationResult
from narrare_core.ai_invocation.pipeline import FinalizedInvocation, PreparedInvocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.prompts.context import PromptContext
from narrare_core.writing._invocation_adapter import build_and_validate_prompt


def _prompt_ctx() -> PromptContext:
    return PromptContext(
        language="en", project_title="Test Novel", genre="fantasy", mode="extend_chapter"
    )


def _composed_prompt() -> ComposedPrompt:
    return ComposedPrompt(system="system prompt", user="user prompt")


def _mock_composer(return_value: ComposedPrompt | None = None) -> MagicMock:
    composer = MagicMock(spec=["build"])
    composer.build = AsyncMock(return_value=return_value or _composed_prompt())
    return composer


def _passing_prepared() -> PreparedInvocation:
    """Real PreparedInvocation so Phase 2 merge can read ``prepared.context``."""
    return PreparedInvocation(
        context=_invocation_ctx(),
        validation=ValidationResult(status=ValidationStatus.PASS),
    )


def _passing_finalized() -> FinalizedInvocation:
    return FinalizedInvocation(
        validation=ValidationResult(status=ValidationStatus.PASS),
    )


def _mock_pipeline_pass() -> MagicMock:
    """Create a mock InvocationPipeline with passing validations."""
    mock = MagicMock(spec=["prepare", "finalize"])
    mock.prepare = AsyncMock(return_value=_passing_prepared())
    mock.finalize = AsyncMock(return_value=_passing_finalized())
    return mock


# ---------------------------------------------------------------------------
# User / Project ID pass-through
# ---------------------------------------------------------------------------


class TestUserProjectIdPassThrough:
    """user_id and project_id flow through to the auto-created context."""

    @pytest.mark.asyncio
    async def test_user_id_and_project_id_reach_prepare(self) -> None:
        """When provided, user_id and project_id are in the auto-created context."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=None,
            user_id="user-abc",
            project_id="proj-xyz",
        )

        ctx = mock_pipeline.prepare.call_args.args[0]
        assert ctx.user_id == "user-abc"
        assert ctx.project_id == "proj-xyz"

    @pytest.mark.asyncio
    async def test_explicit_context_overrides_user_project_ids(self) -> None:
        """When explicit context is given, user_id/project_id from it are used."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()
        explicit_ctx = _invocation_ctx()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=explicit_ctx,
            user_id="should-be-ignored",
            project_id="should-be-ignored",
        )

        ctx = mock_pipeline.prepare.call_args.args[0]
        assert ctx is explicit_ctx
        assert ctx.user_id is None  # explicit context had None

    @pytest.mark.asyncio
    async def test_defaults_to_none_when_not_provided(self) -> None:
        """When no user_id/project_id are given, auto-created context has None."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=None,
        )

        ctx = mock_pipeline.prepare.call_args.args[0]
        assert ctx.user_id is None
        assert ctx.project_id is None


def _invocation_ctx() -> PromptInvocationContext:
    return PromptInvocationContext(feature_id="test-feature", intent=LLMIntent.EXTEND)
