"""Unit tests for ``narrare._app.invocation_context``.

Tests the public helper:
- :func:`build_invocation_context` — creates a ``PromptInvocationContext``
  for wiring invocation evidence into non-writing services.

History:
    The deprecated ``record_invocation_evidence()`` /
    ``safe_record_evidence()`` functions were removed in ADR-048 Slice F.
    The ``safe_compose_invocation()`` wrapper was removed after all callers
    migrated to direct ``compose_invocation`` calls (ADR-048 Q1 follow-up),
    so its tests were removed here too.
"""

from __future__ import annotations

from narrare._app.invocation_context import build_invocation_context
from narrare_core.llm.intents import LLMIntent


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
