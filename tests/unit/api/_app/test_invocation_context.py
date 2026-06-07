"""Unit tests for ``narrare._app.invocation_context``.

Tests the three public helpers:
- :func:`build_invocation_context` — creates a ``PromptInvocationContext``
- :func:`record_invocation_evidence` — runs prepare + finalize on a pipeline
- :func:`safe_record_evidence` — null-safe wrapper that swallows errors
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare._app.invocation_context import (
    build_invocation_context,
    record_invocation_evidence,
    safe_record_evidence,
)
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
# record_invocation_evidence
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_record_invocation_evidence_calls_prepare_and_finalize() -> None:
    """record_invocation_evidence runs both pipeline phases."""
    mock_prepared = MagicMock(spec=object, name="PreparedInvocation")
    mock_finalized = MagicMock(spec=object, name="FinalizedInvocation")
    mock_finalized.evidence_recorded = True

    mock_pipeline = MagicMock(spec=object, name="InvocationPipeline")
    mock_pipeline.prepare = AsyncMock(return_value=mock_prepared)
    mock_pipeline.finalize = AsyncMock(return_value=mock_finalized)

    ctx = build_invocation_context(
        feature_id="test_feature",
        intent=LLMIntent.ANALYSE,
    )

    result = await record_invocation_evidence(mock_pipeline, ctx)

    mock_pipeline.prepare.assert_awaited_once_with(ctx)
    mock_pipeline.finalize.assert_awaited_once()
    assert result is mock_finalized


# ---------------------------------------------------------------------------
# safe_record_evidence
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_safe_record_evidence_noop_when_pipeline_none() -> None:
    """safe_record_evidence returns None silently when pipeline is None."""
    result = await safe_record_evidence(
        None,
        feature_id="test_feature",
        intent=LLMIntent.ANALYSE,
        user_id="u1",
        project_id="p1",
    )

    assert result is None


@pytest.mark.anyio
async def test_safe_record_evidence_records_when_pipeline_provided() -> None:
    """safe_record_evidence delegates to record_invocation_evidence when pipeline exists."""
    mock_prepared = MagicMock(spec=object, name="PreparedInvocation")
    mock_finalized = MagicMock(spec=object, name="FinalizedInvocation")
    mock_finalized.evidence_recorded = False

    mock_pipeline = MagicMock(spec=object, name="InvocationPipeline")
    mock_pipeline.prepare = AsyncMock(return_value=mock_prepared)
    mock_pipeline.finalize = AsyncMock(return_value=mock_finalized)

    await safe_record_evidence(
        mock_pipeline,
        feature_id="kb_extract",
        intent=LLMIntent.KB_EXTRACT,
        user_id="u1",
        project_id="p1",
        language="en",
    )

    mock_pipeline.prepare.assert_awaited_once()
    mock_pipeline.finalize.assert_awaited_once()


@pytest.mark.anyio
async def test_safe_record_evidence_handles_pipeline_errors() -> None:
    """safe_record_evidence swallows exceptions and logs a warning."""
    mock_pipeline = MagicMock(spec=object, name="InvocationPipeline")
    mock_pipeline.prepare = AsyncMock(side_effect=RuntimeError("boom"))

    # Should NOT raise — the error is caught and logged
    await safe_record_evidence(
        mock_pipeline,
        feature_id="failing_feature",
        intent=LLMIntent.CONSISTENCY,
    )
