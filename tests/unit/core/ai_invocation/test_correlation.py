"""Tests for ADR-045 privacy-safe invocation correlation helpers."""

from __future__ import annotations

from narrare_core.ai_invocation.budgets import OutputBudget, OutputBudgetDecision
from narrare_core.ai_invocation.correlation import (
    fingerprint_budget_decision,
    fingerprint_prepared_context,
    fingerprint_prompt,
)
from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt


class TestCorrelationFingerprints:
    """Fingerprints must correlate invocations without storing prose."""

    def test_prepared_context_fingerprint_is_privacy_safe(self) -> None:
        ctx = PromptInvocationContext(
            feature_id="writing/extend",
            intent=LLMIntent.EXTEND,
            dynamic_inputs={"user_preferences": "Never store this raw sentence."},
        )

        fingerprint = fingerprint_prepared_context(ctx)
        dumped = fingerprint.model_dump_json()

        assert "Never store this raw sentence" not in dumped
        assert fingerprint.dynamic_input_keys == ("user_preferences",)
        assert fingerprint.dynamic_input_count == 1

    def test_prompt_fingerprint_excludes_raw_prompt_text(self) -> None:
        prompt = ComposedPrompt(
            system="System prompt with private manuscript details.",
            user="User prose that must not be in evidence.",
        )

        fingerprint = fingerprint_prompt(prompt)
        dumped = fingerprint.model_dump_json()

        assert "private manuscript" not in dumped
        assert "User prose" not in dumped
        assert fingerprint.system_length == len(prompt.system)
        assert fingerprint.user_length == len(prompt.user)

    def test_budget_fingerprint_uses_structured_budget_metadata_only(self) -> None:
        decision = OutputBudgetDecision(
            budget=OutputBudget(max_tokens=16000, profile="comprehensive"),
            source="intent_profile",
            reason="Detailed internal explanation that is not serialized into evidence.",
        )

        fingerprint = fingerprint_budget_decision(decision)
        assert fingerprint is not None
        dumped = fingerprint.model_dump_json()

        assert fingerprint.profile == "comprehensive"
        assert fingerprint.max_output_tokens == 16000
        assert "Detailed internal explanation" not in dumped
