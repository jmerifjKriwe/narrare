"""Regression tests for ADR-045 WebSocket handler modularization."""

from __future__ import annotations

import inspect

from narrare.writing.ws_handler import WritingSessionHandler


def test_ws_handler_stays_below_soft_target_after_split() -> None:
    """The transport handler must stay below the ADR-045 soft target."""
    source_lines = inspect.getsource(WritingSessionHandler).splitlines()

    assert len(source_lines) < 250


def test_ws_handler_constructor_does_not_accept_llm_or_prompt_dependencies() -> None:
    """The handler should depend on a message router, not LLM services."""
    parameters = inspect.signature(WritingSessionHandler).parameters

    assert "message_router" in parameters
    assert "registry" not in parameters
    assert "composer" not in parameters
    assert "config" not in parameters
    assert "invocation_pipeline" not in parameters
    assert "run_limit_resolver" not in parameters
