"""AuthorVoiceAgent — NarrareAgent instantiation + deps + system-prompt wiring
tests (ANAL-007 / ADR-074).

The qualitative half of ADR-074's hybrid metrics strategy (the structural
parallel to ANAL-008's :class:`CharacterVoiceAgent`). The agent produces
:class:`AuthorVoiceOutput` — descriptive-only structured output (binding
boundary: the agent NEVER produces metrics; measurement is deterministic).

This file covers (the rest lives in ``test_author_voice_agent_validation.py``
per the RULE-04 file-size split — files ending in ``_agent.py`` have a 200-line
cap):

    - :class:`AuthorVoiceDeps` contract.
    - :class:`AuthorVoiceAgent` instantiation (system_prompt wiring, RULE-02b).
    - RULE-02b system-prompt wiring (run() takes (prompt, deps) — never
      ``system_prompt``).

See:
    - ADR-074 (Author Voice Storage Contract — boundary invariant).
    - ADR-035 (Agent output validation).
    - ADR-054 (Mode-1 PromptComposer mandate).
"""

from __future__ import annotations

import inspect

from pydantic_ai.models.test import TestModel

from narrare_core.agents.author_voice_agent import AuthorVoiceAgent
from narrare_core.agents.author_voice_types import AuthorVoiceDeps


class TestAuthorVoiceDeps:
    def test_default_construction(self) -> None:
        deps = AuthorVoiceDeps()
        assert deps.chapter_prose == ""
        assert deps.voice_metrics_summary == ""
        assert deps.author_metrics_summary == ""
        assert deps.writing_language == "en"

    def test_carries_runtime_user_channel_content(self) -> None:
        """Deps carry prose + precomputed metrics (RULE-02a category-3 runtime data).

        The agent SEES metrics as input (deps), NEVER produces them as output
        (binding boundary). The same metrics are also formatted into the run
        prompt by the service for the model to interpret.
        """
        deps = AuthorVoiceDeps(
            chapter_prose="She did not turn around.",
            voice_metrics_summary="avg_sent_len=14.3, ttr=0.71, ...",
            author_metrics_summary="dialogue_ratio=0.42, metaphor_density=0.03",
            writing_language="en",
        )
        assert deps.chapter_prose == "She did not turn around."
        assert "avg_sent_len" in deps.voice_metrics_summary
        assert "dialogue_ratio" in deps.author_metrics_summary


class TestAuthorVoiceAgentInstantiation:
    """AuthorVoiceAgent instantiates correctly with / without a system prompt."""

    def test_can_be_instantiated(self) -> None:
        a = AuthorVoiceAgent(model=TestModel())
        assert isinstance(a, AuthorVoiceAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        """The governed author_voice template is passed as system_prompt (Mode 1)."""
        a = AuthorVoiceAgent(
            model=TestModel(),
            system_prompt="RESOLVED-AUTHOR-VOICE-TEMPLATE",
        )
        assert isinstance(a, AuthorVoiceAgent)

    def test_instantiated_without_system_prompt(self) -> None:
        """Agent can be instantiated without a system_prompt (tests)."""
        a = AuthorVoiceAgent(model=TestModel(), system_prompt=None)
        assert isinstance(a, AuthorVoiceAgent)


class TestSystemPromptWiring:
    """The governed template is the system prompt; it reaches the constructor
    (pydantic-ai binds system_prompt at construction, not at run-time)."""

    def test_system_prompt_accepted_at_construction(self) -> None:
        # Must accept system_prompt= at construction without raising.
        a = AuthorVoiceAgent(
            model=TestModel(),
            system_prompt="RESOLVED-AUTHOR-VOICE-TEMPLATE",
        )
        assert a is not None

    def test_run_does_not_accept_system_prompt_kwarg(self) -> None:
        """The system prompt is construction-time only (RULE-02b).

        run() takes (prompt, deps) — never a system_prompt kwarg.
        """
        sig = inspect.signature(AuthorVoiceAgent.run)
        assert "system_prompt" not in sig.parameters
