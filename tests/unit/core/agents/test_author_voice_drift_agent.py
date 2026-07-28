"""Tests for AuthorVoiceDriftAgent — instantiation + RULE-02b Mode-1 loading
(ANAL-009 Phase 2B / ADR-074).

Mirrors the CharacterVoiceDriftAgent test split layout. This file covers
instantiation + RULE-02b Mode-1 template loading (the governed
``author_voice_drift`` template). Sibling files cover the output function
(``test_author_voice_drift_process_output.py``) + the ADR-035 validator
(``test_author_voice_drift_agent_validation.py``).

No real LLM calls (RULE-01b).
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.author_voice_drift_agent import AuthorVoiceDriftAgent


@pytest.fixture()
def agent() -> AuthorVoiceDriftAgent:
    return AuthorVoiceDriftAgent(model=TestModel())


class TestAuthorVoiceDriftAgentInstantiation:
    """AuthorVoiceDriftAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel())
        assert isinstance(agent, AuthorVoiceDriftAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        """The governed author_voice_drift template is passed as system_prompt (Mode 1)."""
        agent = AuthorVoiceDriftAgent(
            model=TestModel(),
            system_prompt="You are an author-voice drift classifier.",
        )
        assert isinstance(agent, AuthorVoiceDriftAgent)

    def test_instantiated_without_system_prompt(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel(), system_prompt=None)
        assert isinstance(agent, AuthorVoiceDriftAgent)

    def test_mode1_system_prompt_is_passed_through_unchanged(self) -> None:
        """RULE-02b: the agent forwards the resolved template verbatim — no inline.

        The agent must NOT synthesise or inline a system prompt; it forwards the
        Mode-1-resolved governed ``author_voice_drift`` template to pydantic-ai
        exactly as received (the Layer-3 service resolves the real template via
        PromptComposer).
        """
        resolved_template = "## System Prompt\n\nYou are an author-voice drift classifier."
        agent = AuthorVoiceDriftAgent(
            model=TestModel(),
            system_prompt=resolved_template,
        )
        sys_prompts = agent._agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert resolved_template in sys_prompts

    def test_no_system_prompt_when_none(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel(), system_prompt=None)
        sys_prompts = agent._agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert not sys_prompts

    def test_output_validator_registered(self) -> None:
        """ADR-035: an output validator is registered on the underlying agent."""
        agent = AuthorVoiceDriftAgent(model=TestModel())
        assert len(agent._agent._output_validators) >= 1  # type: ignore[reportPrivateUsage]

    def test_inherits_run_stream_from_base(self) -> None:
        """RULE-13 (ADR-065): the two-method run/stream interface is provided."""
        agent = AuthorVoiceDriftAgent(model=TestModel())
        assert callable(agent.run)
        assert callable(agent.run_stream)
