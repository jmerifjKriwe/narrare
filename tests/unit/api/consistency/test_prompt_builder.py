"""Unit tests for prompt_builder — token-based truncation and prompt assembly.

Tests the fix for FIND-011: chapters are truncated by token budget
(not character count) so behavior is language-independent.
"""

from __future__ import annotations

from narrare.consistency.prompt_builder import (
    build_consistency_prompt_variables,
)
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
)
from narrare_core.writing._token_utils import default_token_counter

# Default max_chapter_tokens matching the dataclass default in TokenLimitOverrides.
_DEFAULT_CHAPTER_TOKENS = 2000


def _deps(
    chapter_texts: dict[str, str] | None = None,
    kb_summaries: list[dict[str, object]] | None = None,
) -> ConsistencyDeps:
    """Create ConsistencyDeps with sensible defaults for tests."""
    return ConsistencyDeps(
        chapter_texts=chapter_texts or {},
        kb_entity_summaries=kb_summaries or [],
    )


# --- Token-based truncation (FIND-011 regression tests) ---


class TestTokenTruncation:
    """Verify chapter text is truncated by token budget, not characters."""

    def test_text_under_limit_unchanged(self) -> None:
        """Short text should pass through unchanged."""
        text = "The quick brown fox jumps over the lazy dog."
        deps = _deps(chapter_texts={"ch-1": text})
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])[
            "chapter_texts"
        ]
        assert text in result
        # No truncation marker — full text present
        assert result.count(text) == 1

    def test_text_over_limit_truncated_to_token_budget(self) -> None:
        """Long text should be truncated to fit within max_chapter_tokens."""
        # Generate text well over the token limit (~500 words * 1.3 = ~650 tokens,
        # so we need something much larger)
        words = [f"word{i}" for i in range(5000)]
        long_text = " ".join(words)
        original_tokens = default_token_counter(long_text)
        assert original_tokens > _DEFAULT_CHAPTER_TOKENS

        deps = _deps(chapter_texts={"ch-1": long_text})
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])[
            "chapter_texts"
        ]

        # Extract the chapter preview from the result
        # It should be between "### Chapter ch-1\n" and the next "\n##"
        lines = result.split("\n")
        preview_lines: list[str] = []
        capturing = False
        for line in lines:
            if line.startswith("### Chapter ch-1"):
                capturing = True
                continue
            if capturing and (line.startswith("## ") or line.startswith("Check")):
                break
            if capturing:
                preview_lines.append(line)
        preview = "\n".join(preview_lines).strip()

        # Truncated text must be within token budget
        preview_tokens = default_token_counter(preview)
        assert preview_tokens <= _DEFAULT_CHAPTER_TOKENS, (
            f"Preview has {preview_tokens} tokens, exceeds budget of {_DEFAULT_CHAPTER_TOKENS}"
        )

        # Truncated text must be shorter than original
        assert len(preview) < len(long_text)

    def test_custom_max_chapter_tokens_limits_preview(self) -> None:
        """Custom max_chapter_tokens parameter is respected."""
        custom_budget = 50
        words = [f"word{i}" for i in range(500)]
        long_text = " ".join(words)
        assert default_token_counter(long_text) > custom_budget

        deps = _deps(chapter_texts={"ch-1": long_text})
        result = build_consistency_prompt_variables(
            deps,
            [ConsistencyCheckType.CHARACTER],
            max_chapter_tokens=custom_budget,
        )["chapter_texts"]

        # Extract preview
        lines = result.split("\n")
        preview_lines: list[str] = []
        capturing = False
        for line in lines:
            if line.startswith("### Chapter ch-1"):
                capturing = True
                continue
            if capturing and (line.startswith("## ") or line.startswith("Check")):
                break
            if capturing:
                preview_lines.append(line)
        preview = "\n".join(preview_lines).strip()

        preview_tokens = default_token_counter(preview)
        assert preview_tokens <= custom_budget, (
            f"Preview has {preview_tokens} tokens, exceeds custom budget of {custom_budget}"
        )

    def test_empty_text_returns_empty_preview(self) -> None:
        """Empty chapter text should produce an empty chapter section."""
        deps = _deps(chapter_texts={"ch-1": ""})
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])[
            "chapter_texts"
        ]
        assert "### Chapter ch-1" in result
        # Empty text → empty line after chapter header
        assert "word0" not in result

    def test_non_ascii_text_truncated_correctly(self) -> None:
        """German text with umlauts truncates by tokens, not characters."""
        # German text: Über die schöne Bäckerei repeated to exceed budget
        base = "Über die schöne Bäckerei in der Fußgängerzone "
        # Repeat until well over the token budget
        repeats = int(_DEFAULT_CHAPTER_TOKENS * 2 / default_token_counter(base)) + 2
        long_german = base * repeats

        original_tokens = default_token_counter(long_german)
        assert original_tokens > _DEFAULT_CHAPTER_TOKENS

        deps = _deps(chapter_texts={"ch-1": long_german})
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])[
            "chapter_texts"
        ]

        # Extract preview (same logic as above)
        lines = result.split("\n")
        preview_lines: list[str] = []
        capturing = False
        for line in lines:
            if line.startswith("### Chapter ch-1"):
                capturing = True
                continue
            if capturing and (line.startswith("## ") or line.startswith("Check")):
                break
            if capturing:
                preview_lines.append(line)
        preview = "\n".join(preview_lines).strip()

        preview_tokens = default_token_counter(preview)
        assert preview_tokens <= _DEFAULT_CHAPTER_TOKENS, (
            f"German preview has {preview_tokens} tokens, "
            f"exceeds budget of {_DEFAULT_CHAPTER_TOKENS}"
        )

    def test_no_character_based_hardcoded_truncation(self) -> None:
        """Verify we don't regress to character-based truncation.

        A string of 2001 characters should NOT be cut at position 2000.
        Instead, truncation should happen at word boundaries based on tokens.
        """
        # Exactly 2001 characters (old threshold was 2000 chars)
        text_2001 = "a" * 2001
        deps = _deps(chapter_texts={"ch-1": text_2001})
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])[
            "chapter_texts"
        ]

        # With 2001 chars as a single word, tokens = 2001 * 1.3 = 2601
        # This exceeds 2000 tokens, so it should be truncated — but
        # NOT at position 2000. It truncates at word level.
        # Since it's one giant word, cap_to_budget will truncate it
        # to fit the token budget (either empty or the word if it fits).
        # The key assertion: the result should NOT contain exactly 2000 chars
        # of the original text (which the old code would do).
        assert "a" * 2000 not in result or result.count("a") != 2000


# --- Prompt assembly ---


class TestBuildConsistencyPromptVariables:
    """Tests for runtime data formatting for PromptComposer variables."""

    def test_includes_all_chapters(self) -> None:
        """All chapter IDs appear in the prompt."""
        deps = _deps(chapter_texts={"ch-1": "Hello", "ch-2": "World"})
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])
        assert "### Chapter ch-1" in result["chapter_texts"]
        assert "### Chapter ch-2" in result["chapter_texts"]

    def test_includes_kb_entities(self) -> None:
        """KB entity summaries appear in the prompt."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Alice", "fields": {"age": "25"}},
        ]
        deps = _deps(kb_summaries=summaries)
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])
        assert "Alice" in result["kb_entities"]
        assert "[character]" in result["kb_entities"]

    def test_includes_kb_relationships(self) -> None:
        """KB relationship descriptions appear in the prompt variables (FIND-001)."""
        formatted = "Aria → [enemy_of] → Malachai"
        deps = ConsistencyDeps(kb_relationships=formatted)
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])
        assert "kb_relationships" in result
        assert result["kb_relationships"] == formatted

    def test_includes_check_types(self) -> None:
        """Requested check types appear in the prompt."""
        deps = _deps()
        result = build_consistency_prompt_variables(
            deps,
            [ConsistencyCheckType.CHARACTER, ConsistencyCheckType.TIMELINE],
        )
        assert result["check_types"] == "character, timeline"

    def test_empty_deps_produces_empty_runtime_variables(self) -> None:
        """Empty deps produce empty data variables, not inline instructions."""
        deps = _deps()
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])
        assert result["chapter_texts"] == ""
        assert result["kb_entities"] == ""
        assert result["check_types"] == "character"

    def test_runtime_variables_do_not_include_inline_task_body(self) -> None:
        """Prompt body instructions stay in bundled templates, not API fallbacks."""
        deps = _deps(chapter_texts={"ch-1": "Hello"})
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])

        combined = "\n".join(result.values())
        assert "You are a consistency checker" not in combined
        assert "Analyze the chapters" not in combined
        assert "Return structured findings" not in combined
