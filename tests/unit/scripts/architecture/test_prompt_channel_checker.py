"""Tests for RULE-02b checker: prompt-channel injection (prompt_channel.py).

ADR-046 D.2 Module 3.
"""

from __future__ import annotations

import ast

from scripts.architecture.checkers import check_prompt_channel_injection


def _parse(source: str) -> ast.AST:
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    return source.splitlines()


# =====================================================================
# Concatenation (BinOp Add) detection
# =====================================================================


class TestConcatenationFlagged:
    """``composed.system + composed.user`` IS flagged."""

    def test_simple_concatenation_flagged(self) -> None:
        source = "full_prompt = composed.system + composed.user\n"
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].rule == "RULE-02b"
        assert "concatenated" in violations[0].detail

    def test_concatenation_with_separator_flagged(self) -> None:
        # The exact CR-AUFG-02-04 pattern (binop form).
        source = 'full_prompt = composed.system + "\\n\\n" + composed.user\n'
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1

    def test_concatenation_self_attr_flagged(self) -> None:
        source = "prompt = self.composer.build(ctx).system + self.composer.build(ctx).user\n"
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1


# =====================================================================
# f-string detection
# =====================================================================


class TestFStringFlagged:
    """f-strings interpolating both .system and .user ARE flagged."""

    def test_fstring_both_channels_flagged(self) -> None:
        # The exact CR-AUFG-02-04 pattern (f-string form).
        source = 'full_prompt = f"{composed.system}\\n\\n{composed.user}"\n'
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "f-string" in violations[0].detail

    def test_fstring_system_only_not_flagged(self) -> None:
        source = 'log_msg = f"system prompt: {composed.system}"\n'
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_fstring_user_only_not_flagged(self) -> None:
        source = 'log_msg = f"user prompt: {composed.user}"\n'
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# Correct patterns NOT flagged
# =====================================================================


class TestCorrectPatternsNotFlagged:
    """Tuple returns and separate channel passing are NOT flagged."""

    def test_tuple_return_parens_not_flagged(self) -> None:
        # The fixed writing_graph_prompts.py pattern.
        source = "return (composed.system, composed.user)\n"
        violations = check_prompt_channel_injection(
            "packages/core/narrare_core/agents/writing_graph_prompts.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_tuple_return_no_parens_not_flagged(self) -> None:
        # The consistency/prompt_builder.py pattern.
        source = "return composed.system, composed.user\n"
        violations = check_prompt_channel_injection(
            "apps/api/narrare/consistency/prompt_builder.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_separate_channel_passing_not_flagged(self) -> None:
        # The fixed ChatService pattern.
        source = (
            "agent = ChatAgent(model=model, system_prompt=composed.system or None)\n"
            "result = await agent.run(prompt=composed.user)\n"
        )
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_unrelated_string_concat_not_flagged(self) -> None:
        source = "msg = greeting + name\n"
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# Scope filtering — exempt paths
# =====================================================================


class TestScopeFiltering:
    """core/prompts/ and tests are NOT checked."""

    def test_core_prompts_not_checked(self) -> None:
        source = "combined = composed.system + composed.user\n"
        violations = check_prompt_channel_injection(
            "packages/core/narrare_core/prompts/composer.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_test_files_not_checked(self) -> None:
        source = "combined = composed.system + composed.user\n"
        violations = check_prompt_channel_injection(
            "tests/unit/api/chat/test_chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_type_checking_block_not_checked(self) -> None:
        source = (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    combined = composed.system + composed.user\n"
        )
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# Approved exceptions
# =====================================================================


class TestApprovedExceptions:
    def test_approval_marker_accepted(self) -> None:
        source = (
            '# narrare: allow reason="temporary migration measure"\n'
            "full_prompt = composed.system + composed.user\n"
        )
        violations = check_prompt_channel_injection(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].approved is True
        assert "migration" in violations[0].approval_reason
