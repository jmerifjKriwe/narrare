"""Tests for the inline prompt checker (RULE-INLINE).

Validates detection of unregistered inline prompt strings, exemption
of registered fallbacks, and path-based exclusions.
"""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path as _Path
from unittest.mock import patch

_ROOT = str(_Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.architecture._checkers.inline_prompts import (  # noqa: E402
    _is_exempt_path,
    _is_prompt_like,
    check_inline_prompts,
)

# ── Fixtures ───────────────────────────────────────────────────────


def _parse(source: str) -> tuple[ast.AST, list[str]]:
    tree = ast.parse(textwrap.dedent(source))
    lines = textwrap.dedent(source).splitlines()
    return tree, lines


# ── _is_prompt_like ────────────────────────────────────────────────


class TestIsPromptLike:
    def test_detects_you_are(self) -> None:
        assert _is_prompt_like("You are a helpful assistant.")

    def test_detects_your_task(self) -> None:
        assert _is_prompt_like("Your task is to write a story.")

    def test_detects_your_job(self) -> None:
        assert _is_prompt_like("Your job is to review text.")

    def test_detects_act_as(self) -> None:
        assert _is_prompt_like("Act as a creative writing coach.")

    def test_detects_you_work(self) -> None:
        assert _is_prompt_like("You work as an editor.")

    def test_detects_system_prompt(self) -> None:
        assert _is_prompt_like("This is the system prompt for the agent.")

    def test_rejects_short_non_prompt(self) -> None:
        assert not _is_prompt_like("The quick brown fox jumps over the lazy dog.")

    def test_case_insensitive(self) -> None:
        assert _is_prompt_like("YOU ARE THE BEST.")

    def test_rejects_random_text(self) -> None:
        assert not _is_prompt_like("Calculate the sum of two numbers and return result.")


# ── _is_exempt_path ────────────────────────────────────────────────


class TestIsExemptPath:
    def test_exempt_core_prompts(self) -> None:
        assert _is_exempt_path("packages/core/narrare_core/prompts/composer.py")

    def test_exempt_test_file(self) -> None:
        assert _is_exempt_path("tests/unit/core/test_something.py")

    def test_exempt_conftest(self) -> None:
        assert _is_exempt_path("tests/conftest.py")

    def test_not_exempt_service(self) -> None:
        assert not _is_exempt_path("apps/api/narrare/kb/service.py")

    def test_not_exempt_agents(self) -> None:
        assert not _is_exempt_path("packages/core/narrare_core/agents/my_agent.py")


# ── check_inline_prompts — detection ───────────────────────────────


class TestCheckInlinePromptsDetection:
    def test_detects_long_inline_prompt(self) -> None:
        source = '''\
        MY_PROMPT = """You are a creative writing assistant. Your job is to help
        authors develop their stories by providing detailed feedback on plot,
        character development, pacing, and worldbuilding elements."""
        '''
        tree, lines = _parse(source)
        violations = check_inline_prompts("apps/api/narrare/writing/service.py", tree, lines)
        assert len(violations) == 1
        assert violations[0].rule == "RULE-INLINE"
        assert not violations[0].approved

    def test_short_string_not_detected(self) -> None:
        source = """\
        MSG = "You are awesome!"
        """
        tree, lines = _parse(source)
        violations = check_inline_prompts("apps/api/narrare/writing/service.py", tree, lines)
        assert len(violations) == 0

    def test_non_prompt_long_string_not_detected(self) -> None:
        source = '''\
        LONG_TEXT = """This is a very long string that exceeds one hundred characters
        in total length but does not contain any prompt-like patterns whatsoever.
        It's just a regular data string used for some other purpose."""
        '''
        tree, lines = _parse(source)
        violations = check_inline_prompts("apps/api/narrare/some/module.py", tree, lines)
        assert len(violations) == 0

    def test_exempt_path_skips_check(self) -> None:
        source = '''\
        MY_PROMPT = """You are a creative writing assistant. Your job is to help
        authors develop their stories by providing detailed feedback on plot,
        character development, pacing, and worldbuilding elements."""
        '''
        tree, lines = _parse(source)
        violations = check_inline_prompts(
            "packages/core/narrare_core/prompts/builder.py", tree, lines
        )
        assert len(violations) == 0

    def test_test_file_skips_check(self) -> None:
        source = '''\
        TEST_PROMPT = """You are a test assistant. Your task is to respond with
        a fixed answer for testing purposes. This prompt is used only in tests."""
        '''
        tree, lines = _parse(source)
        violations = check_inline_prompts("tests/unit/api/test_service.py", tree, lines)
        assert len(violations) == 0

    def test_string_concatenation_detected(self) -> None:
        long_source = (
            'PROMPT = ("You are a helpful assistant that specializes '
            'in creative writing. " + "Your task is to write '
            'compelling stories with rich characters.")'
        )
        tree, lines = _parse(long_source)
        violations = check_inline_prompts("apps/api/narrare/some/service.py", tree, lines)
        assert len(violations) == 1


# ── check_inline_prompts — registration ────────────────────────────


class TestCheckInlinePromptsRegistration:
    """Tests that registered fallbacks are approved, not violations."""

    def test_registered_variable_approved(self) -> None:
        """A registered inline prompt is emitted as approved, not a violation."""
        source = '''\
        CONSISTENCY_SYSTEM_PROMPT = """You are a consistency checker for a creative
        writing project. Your job is to detect contradictions and inconsistencies
        across chapters and entity data. Be thorough but fair."""
        '''
        tree, lines = _parse(source)
        fake_registry = [
            {
                "file": "apps/api/narrare/consistency/prompt_builder.py",
                "variable": "CONSISTENCY_SYSTEM_PROMPT",
                "reason": "Registered inline fallback",
            }
        ]
        with patch(
            "scripts.architecture._checkers.inline_prompts._load_registered_fallbacks",
            return_value=fake_registry,
        ):
            violations = check_inline_prompts(
                "apps/api/narrare/consistency/prompt_builder.py", tree, lines
            )
        assert len(violations) == 1
        assert violations[0].approved
        assert "Registered" in violations[0].detail

    def test_unregistered_variable_in_registered_file_is_violation(self) -> None:
        """An unregistered prompt in a file with other registrations is a violation
        if the variable name doesn't match any entry."""
        source = '''\
        DIFFERENT_PROMPT = """You are a completely different assistant. Your job is
        to do something else entirely. This is not the registered prompt."""
        '''
        tree, lines = _parse(source)
        fake_registry = [
            {
                "file": "apps/api/narrare/consistency/prompt_builder.py",
                "variable": "CONSISTENCY_SYSTEM_PROMPT",
                "reason": "Only CONSISTENCY_SYSTEM_PROMPT is registered",
            }
        ]
        with patch(
            "scripts.architecture._checkers.inline_prompts._load_registered_fallbacks",
            return_value=fake_registry,
        ):
            violations = check_inline_prompts(
                "apps/api/narrare/consistency/prompt_builder.py", tree, lines
            )
        # DIFFERENT_PROMPT doesn't match the registered CONSISTENCY_SYSTEM_PROMPT
        assert len(violations) == 1
        assert not violations[0].approved
