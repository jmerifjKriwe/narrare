"""Unit tests for ``narrare._app.invocation_context``.

Tests the public helpers:
- :func:`build_invocation_context` — creates a ``PromptInvocationContext``
- :func:`safe_compose_invocation` — null-safe wrapper that composes
  invocations through the pipeline (Mode 2) and swallows errors

The deprecated ``record_invocation_evidence()`` and
``safe_record_evidence()`` functions were removed in ADR-048 Slice F.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare._app.invocation_context import (
    build_invocation_context,
    safe_compose_invocation,
)
from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration
from narrare_core.llm.intents import LLMIntent

# ---------------------------------------------------------------------------
# build_invocation_context
# ---------------------------------------------------------------------------


def test_build_invocation_context_creates_context() -> None:
    """build_invocation_context returns a PromptInvocationContext with the correct fields."""
    ctx = build_invocation_context(
        feature_id="kb_extract",
        intent=LLMIntent.KB_EXTRACT,
        user_id="user-123",
        project_id="proj-456",
        language="de",
    )

    assert ctx.feature_id == "kb_extract"
    assert ctx.intent == LLMIntent.KB_EXTRACT
    assert ctx.user_id == "user-123"
    assert ctx.project_id == "proj-456"
    assert ctx.language == "de"


def test_build_invocation_context_defaults() -> None:
    """build_invocation_context applies defaults for optional fields."""
    ctx = build_invocation_context(
        feature_id="analysis_beta_read",
        intent=LLMIntent.BETA_READ,
    )

    assert ctx.feature_id == "analysis_beta_read"
    assert ctx.user_id is None
    assert ctx.project_id is None
    assert ctx.language == "en"


# ---------------------------------------------------------------------------
# safe_compose_invocation
# ---------------------------------------------------------------------------


def _make_manual_injection() -> ManualInjectionDeclaration:
    """Create a valid ManualInjectionDeclaration for tests."""
    return ManualInjectionDeclaration(
        reason="Agent composes prompt internally from deps.",
        variables=("chapter_text",),
        injection_mechanism="agent_deps",
    )


@pytest.mark.anyio
async def test_safe_compose_invocation_noop_when_pipeline_none() -> None:
    """safe_compose_invocation returns None silently when pipeline is None."""
    result = await safe_compose_invocation(
        None,
        feature_id="test_feature",
        intent=LLMIntent.ANALYSE,
        user_id="u1",
        project_id="p1",
        manual_injection=_make_manual_injection(),
    )

    assert result is None


@pytest.mark.anyio
async def test_safe_compose_invocation_calls_compose_when_pipeline_provided() -> None:
    """safe_compose_invocation delegates to compose_invocation when pipeline exists."""
    mock_pipeline = MagicMock(spec=object, name="InvocationPipeline")

    with patch(
        "narrare_core.ai_invocation.compose_invocation",
        new_callable=AsyncMock,
    ) as mock_compose:
        await safe_compose_invocation(
            mock_pipeline,
            feature_id="kb_extract",
            intent=LLMIntent.KB_EXTRACT,
            user_id="u1",
            project_id="p1",
            language="en",
            manual_injection=_make_manual_injection(),
        )

    mock_compose.assert_awaited_once()
    # Verify the pipeline was passed through
    call_kwargs = mock_compose.call_args.kwargs
    assert call_kwargs["invocation_pipeline"] is mock_pipeline
    assert call_kwargs["manual_injection"] is not None


@pytest.mark.anyio
async def test_safe_compose_invocation_handles_composition_errors() -> None:
    """safe_compose_invocation swallows exceptions and logs a warning."""
    mock_pipeline = MagicMock(spec=object, name="InvocationPipeline")

    with patch(
        "narrare_core.ai_invocation.compose_invocation",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ):
        # Should NOT raise — the error is caught and logged
        await safe_compose_invocation(
            mock_pipeline,
            feature_id="failing_feature",
            intent=LLMIntent.CONSISTENCY,
            manual_injection=_make_manual_injection(),
        )
