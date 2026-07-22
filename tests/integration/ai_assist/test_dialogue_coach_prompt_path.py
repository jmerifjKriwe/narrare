"""ADR-046 §D.1 prompt-path compliance test for dialogue_coach.

Verifies that the resolving service uses Mode 1 (PromptComposer) and
never an inline f-string feature prompt. Closes the prompt-path-compliance
gate declared in adoption-registry.yaml (Task 9).
"""

from __future__ import annotations

import inspect

from narrare.ai_assist.service import DialogueCoachService


class TestDialogueCoachPromptPathCompliance:
    """ADR-046 §D.1 + ADR-054 — Mode 1 resolution, no inline f-string."""

    def test_service_does_not_build_feature_prompt_via_fstring(self) -> None:
        """The service source MUST NOT assemble a 'Generate ...' / 'Analyse
        ...' feature prompt via f-string. Feature framing flows through
        PromptComposer + the governed template (Task 8).

        This is a source-level smoke check. The definitive guard is
        ``_check_inline_feature_prompt.py`` (architecture gate), which
        scans every service for the anti-pattern.
        """
        source = inspect.getsource(DialogueCoachService)
        # The service MUST reference compose_invocation or
        # resolve_dialogue_coach_prompt (Mode 1):
        assert "resolve_dialogue_coach_prompt" in source or "compose_invocation" in source
        # The service MUST NOT build an f-string feature framing:
        assert 'f"Generate' not in source
        assert 'f"Analyse' not in source
        assert 'f"Improve' not in source

    def test_service_uses_llmintent_dialogue_coach(self) -> None:
        """The service references LLMIntent.DIALOGUE_COACH (directly or via
        the _prompt helper)."""
        from narrare.ai_assist import _prompt

        source = inspect.getsource(_prompt)
        assert "LLMIntent.DIALOGUE_COACH" in source
