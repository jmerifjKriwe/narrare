"""Tests for InterviewQuestionAgent (AUFG-03-01).

Covers:
- ADR-026 capability guarantee: ``NarrareMeta`` / ``NarrareUniversalRules``
  / ``NarrareObservability`` are auto-injected, mirroring the
  ``test_chat_agent.TestChatAgentCapabilities`` regression guard.
- Construction contract: ``InterviewDeps`` is the deps_type, ``str`` is
  the output_type, ``HistoryPolicy.NONE`` is the default (single-shot).
"""

from __future__ import annotations

from typing import Any

import pytest

from narrare_core.agents.interview_question_agent import (
    InterviewDeps,
    InterviewQuestionAgent,
)


def _install_capturing_agent(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch narrare_core.agents.base.Agent to record its constructor kwargs.

    Returns the shared dict that the CapturingPydanticAgent instances write
    into. Mirrors the canonical pattern from test_chat_agent.py /
    tests/unit/core/agents/test_base.py.
    """
    import narrare_core.agents.base as base_module

    captured: dict[str, Any] = {}

    class CapturingPydanticAgent:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def output_validator(self, validator: Any) -> Any:
            return validator

        def tool(self, tool_func: Any) -> Any:
            return tool_func

    monkeypatch.setattr(base_module, "Agent", CapturingPydanticAgent)
    return captured


class TestInterviewQuestionAgentConstruction:
    """Construction matches the documented single-shot task-agent shape."""

    def test_inherits_from_narrareagent(self) -> None:
        from narrare_core.agents.base import NarrareAgent

        assert issubclass(InterviewQuestionAgent, NarrareAgent)

    def test_deps_type_is_interview_deps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _install_capturing_agent(monkeypatch)
        agent_cls: Any = InterviewQuestionAgent
        agent_cls(model=object())
        assert captured["deps_type"] is InterviewDeps

    def test_system_prompt_forwarded_to_pydantic_agent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _install_capturing_agent(monkeypatch)
        marker = "INTERVIEW_FEATURE_SYSTEM_PROMPT"
        agent_cls: Any = InterviewQuestionAgent
        agent_cls(model=object(), system_prompt=marker)
        assert captured["system_prompt"] == marker

    def test_system_prompt_none_omitted_from_kwargs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _install_capturing_agent(monkeypatch)
        agent_cls: Any = InterviewQuestionAgent
        agent_cls(model=object(), system_prompt=None)
        # None system_prompt is omitted so the guaranteed capabilities
        # alone define the system layer (mirrors ChatAgent).
        assert captured.get("system_prompt") is None


class TestInterviewDeps:
    """InterviewDeps carries the lightweight runtime context."""

    def test_defaults(self) -> None:
        deps = InterviewDeps()
        assert deps.language == "en"
        assert deps.user_id is None
        assert deps.project_id is None

    def test_explicit_values(self) -> None:
        deps = InterviewDeps(language="de", user_id="u1", project_id="p1")
        assert deps.language == "de"
        assert deps.user_id == "u1"
        assert deps.project_id == "p1"


class TestInterviewQuestionAgentCapabilities:
    """ADR-026 / AUFG-03-01: guaranteed capabilities are auto-injected.

    The whole point of the AUFG-03-01 migration is that the interview
    path now flows through ``NarrareAgent`` so the three guaranteed
    capabilities (``NarrareMeta`` / ``NarrareUniversalRules`` /
    ``NarrareObservability``) are present — previously, when the path
    called ``ModelRegistry.run()`` directly, none of them were.
    """

    @pytest.mark.parametrize("system_prompt", ["FEATURE_SYSTEM_PROMPT", None])
    def test_guaranteed_capabilities_retained_with_or_without_system_prompt(
        self,
        system_prompt: str | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NarrareMeta + NarrareUniversalRules + NarrareObservability survive."""
        captured = _install_capturing_agent(monkeypatch)
        from narrare_core.agents.capabilities import (
            NarrareMeta,
            NarrareObservability,
            NarrareUniversalRules,
        )

        agent_cls: Any = InterviewQuestionAgent
        agent_cls(model=object(), system_prompt=system_prompt)

        assert captured, "InterviewQuestionAgent did not reach the NarrareAgent base constructor."
        capabilities: Any = captured["capabilities"]
        capability_types: set[type[Any]] = {type(capability) for capability in capabilities}
        assert NarrareMeta in capability_types, (
            "InterviewQuestionAgent must inject NarrareMeta (the migration's whole point)."
        )
        assert NarrareUniversalRules in capability_types, (
            "InterviewQuestionAgent must inject NarrareUniversalRules."
        )
        assert NarrareObservability in capability_types, (
            "InterviewQuestionAgent must inject NarrareObservability."
        )
