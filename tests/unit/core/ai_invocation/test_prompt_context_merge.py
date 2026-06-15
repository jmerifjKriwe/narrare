"""Regression tests for ADR-045 prompt-context merge semantics."""

from __future__ import annotations

from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.ai_invocation.prompt_context_merge import (
    PromptContextMergeStatus,
    merge_prepared_dynamic_inputs,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext


def _context(dynamic_inputs: dict[str, str]) -> PromptInvocationContext:
    return PromptInvocationContext(
        feature_id="writing/extend",
        intent=LLMIntent.EXTEND,
        dynamic_inputs=dynamic_inputs,
    )


class TestPromptContextMerge:
    """Prepared dynamic inputs must become the canonical PromptContext."""

    def test_fills_empty_prompt_context_field(self) -> None:
        prompt_context = PromptContext(language="en", mode="extend")
        result = merge_prepared_dynamic_inputs(
            prompt_context, _context({"user_preferences": "pref"})
        )

        assert result.context.user_preferences == "pref"
        assert result.entries["user_preferences"].status == PromptContextMergeStatus.MERGED

    def test_preserves_higher_precedence_existing_field(self) -> None:
        prompt_context = PromptContext(
            language="en",
            mode="extend",
            author_instructions="Use the explicit instruction.",
        )
        result = merge_prepared_dynamic_inputs(
            prompt_context,
            _context({"author_instructions": "Generated lower precedence instruction."}),
        )

        assert result.context.author_instructions == "Use the explicit instruction."
        assert result.entries["author_instructions"].status == (
            PromptContextMergeStatus.ALREADY_PROVIDED
        )

    def test_feature_specific_key_lands_in_extra(self) -> None:
        prompt_context = PromptContext(language="en", mode="extend")
        result = merge_prepared_dynamic_inputs(
            prompt_context, _context({"kb_suggested": "candidate"})
        )

        assert result.context.extra["kb_suggested"] == "candidate"
        assert result.entries["kb_suggested"].status == PromptContextMergeStatus.MERGED

    def test_feature_specific_existing_extra_is_preserved(self) -> None:
        prompt_context = PromptContext(
            language="en",
            mode="extend",
            extra={"kb_suggested": "assembler candidate"},
        )
        result = merge_prepared_dynamic_inputs(
            prompt_context,
            _context({"kb_suggested": "enricher candidate"}),
        )

        assert result.context.extra["kb_suggested"] == "assembler candidate"
        assert result.entries["kb_suggested"].status == PromptContextMergeStatus.ALREADY_PROVIDED
