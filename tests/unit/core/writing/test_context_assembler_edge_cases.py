"""Tests for context_assembler.py — frontmatter edge cases and truncation utilities.

Split from test_context_assembler_overflow.py for RULE-04 compliance.

Covers:
1. Malformed YAML frontmatter — no crash, empty references
2. Frontmatter with only non-KB keys — empty references
3. Frontmatter with empty YAML values — empty references
4. ``_truncate_to_budget`` with zero/negative limit
5. ``_enforce_budget`` with text within and over limit
"""

from __future__ import annotations

import pytest
import yaml

from narrare_core.writing.context_assembler import WritingContextAssembler


def _frontmatter(**fields: object) -> str:
    yaml_str = yaml.dump(dict(fields), default_flow_style=False)
    return f"---\n{yaml_str}---\n"


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    return WritingContextAssembler(total_budget=6000)


class TestFrontmatterEdgeCases:
    """Bad, missing, or empty frontmatter extracts no KB references."""

    @pytest.mark.asyncio
    async def test_malformed_yaml_no_crash(self, assembler: WritingContextAssembler) -> None:
        ctx = await assembler.assemble(
            chapter_content="x", chapter_frontmatter="---\nkey: value\n  broken: yes\n---"
        )
        assert ctx.kb_characters == ""

    @pytest.mark.asyncio
    async def test_non_kb_keys_return_empty(self, assembler: WritingContextAssembler) -> None:
        ctx = await assembler.assemble(
            chapter_content="x", chapter_frontmatter=_frontmatter(title="Chapter One")
        )
        assert ctx.kb_characters == ""

    @pytest.mark.asyncio
    async def test_empty_values_return_empty(self, assembler: WritingContextAssembler) -> None:
        ctx = await assembler.assemble(
            chapter_content="x", chapter_frontmatter="---\ncharacters:\n---"
        )
        assert ctx.kb_characters == ""


class TestTruncateToBudget:
    """Edge cases for ``_truncate_to_budget`` and ``_enforce_budget``."""

    def test_zero_limit_returns_empty(self) -> None:
        asm = WritingContextAssembler()
        assert asm._truncate_to_budget("hello world", 0) == ""

    def test_negative_limit_returns_empty(self) -> None:
        asm = WritingContextAssembler()
        assert asm._truncate_to_budget("hello world", -5) == ""

    def test_within_budget_returns_text_unchanged(self) -> None:
        asm = WritingContextAssembler()
        assert asm._truncate_to_budget("hello", 100) == "hello"

    def test_enforce_budget_within_limit_returns_overflow(self) -> None:
        asm = WritingContextAssembler()
        result, overflow = asm._enforce_budget("hi", 100)
        assert result == "hi"
        assert overflow > 0

    def test_enforce_budget_over_limit_truncates(self) -> None:
        asm = WritingContextAssembler()
        # "hello world foo bar" = 5 tokens; limit=3 triggers truncation
        result, overflow = asm._enforce_budget("hello world foo bar", 3)
        assert result != "hello world foo bar"
        assert overflow == 0
