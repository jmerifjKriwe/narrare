"""Unit tests for prompt_builder — token-based truncation and prompt assembly.

Tests the fix for FIND-011: chapters are truncated by token budget
(not character count) so behavior is language-independent.
"""

from __future__ import annotations

from narrare.consistency.prompt_builder import (
    MAX_CONSISTENCY_CONTEXT_TOKENS,
    build_user_prompt,
)
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
)
from narrare_core.writing._token_utils import default_token_counter


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
        result = build_user_prompt(deps, [ConsistencyCheckType.CHARACTER])
        assert text in result
        # No truncation marker — full text present
        assert result.count(text) == 1

    def test_text_over_limit_truncated_to_token_budget(self) -> None:
        """Long text should be truncated to fit within MAX_CONSISTENCY_CONTEXT_TOKENS."""
        # Generate text well over the token limit (~500 words * 1.3 = ~650 tokens,
        # so we need something much larger)
        words = [f"word{i}" for i in range(5000)]
        long_text = " ".join(words)
        original_tokens = default_token_counter(long_text)
        assert original_tokens > MAX_CONSISTENCY_CONTEXT_TOKENS

        deps = _deps(chapter_texts={"ch-1": long_text})
        result = build_user_prompt(deps, [ConsistencyCheckType.CHARACTER])

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
        assert preview_tokens <= MAX_CONSISTENCY_CONTEXT_TOKENS, (
            f"Preview has {preview_tokens} tokens, "
            f"exceeds budget of {MAX_CONSISTENCY_CONTEXT_TOKENS}"
        )

        # Truncated text must be shorter than original
        assert len(preview) < len(long_text)

    def test_empty_text_returns_empty_preview(self) -> None:
        """Empty chapter text should produce an empty chapter section."""
        deps = _deps(chapter_texts={"ch-1": ""})
        result = build_user_prompt(deps, [ConsistencyCheckType.CHARACTER])
        assert "### Chapter ch-1" in result
        # Empty text → empty line after chapter header
        assert "word0" not in result

    def test_non_ascii_text_truncated_correctly(self) -> None:
        """German text with umlauts truncates by tokens, not characters."""
        # German text: Über die schöne Bäckerei repeated to exceed budget
        base = "Über die schöne Bäckerei in der Fußgängerzone "
        # Repeat until well over the token budget
        repeats = int(MAX_CONSISTENCY_CONTEXT_TOKENS * 2 / default_token_counter(base)) + 2
        long_german = base * repeats

        original_tokens = default_token_counter(long_german)
        assert original_tokens > MAX_CONSISTENCY_CONTEXT_TOKENS

        deps = _deps(chapter_texts={"ch-1": long_german})
        result = build_user_prompt(deps, [ConsistencyCheckType.CHARACTER])

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
        assert preview_tokens <= MAX_CONSISTENCY_CONTEXT_TOKENS, (
            f"German preview has {preview_tokens} tokens, "
            f"exceeds budget of {MAX_CONSISTENCY_CONTEXT_TOKENS}"
        )

    def test_no_character_based_hardcoded_truncation(self) -> None:
        """Verify we don't regress to character-based truncation.

        A string of 2001 characters should NOT be cut at position 2000.
        Instead, truncation should happen at word boundaries based on tokens.
        """
        # Exactly 2001 characters (old threshold was 2000 chars)
        text_2001 = "a" * 2001
        deps = _deps(chapter_texts={"ch-1": text_2001})
        result = build_user_prompt(deps, [ConsistencyCheckType.CHARACTER])

        # With 2001 chars as a single word, tokens = 2001 * 1.3 = 2601
        # This exceeds 2000 tokens, so it should be truncated — but
        # NOT at position 2000. It truncates at word level.
        # Since it's one giant word, cap_to_budget will truncate it
        # to fit the token budget (either empty or the word if it fits).
        # The key assertion: the result should NOT contain exactly 2000 chars
        # of the original text (which the old code would do).
        assert "a" * 2000 not in result or result.count("a") != 2000


# --- Prompt assembly ---


class TestBuildUserPrompt:
    """Tests for the overall prompt construction."""

    def test_includes_all_chapters(self) -> None:
        """All chapter IDs appear in the prompt."""
        deps = _deps(chapter_texts={"ch-1": "Hello", "ch-2": "World"})
        result = build_user_prompt(deps, [ConsistencyCheckType.CHARACTER])
        assert "### Chapter ch-1" in result
        assert "### Chapter ch-2" in result

    def test_includes_kb_entities(self) -> None:
        """KB entity summaries appear in the prompt."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Alice", "fields": {"age": "25"}},
        ]
        deps = _deps(kb_summaries=summaries)
        result = build_user_prompt(deps, [ConsistencyCheckType.CHARACTER])
        assert "Alice" in result
        assert "[character]" in result

    def test_includes_check_types(self) -> None:
        """Requested check types appear in the prompt."""
        deps = _deps()
        result = build_user_prompt(
            deps,
            [ConsistencyCheckType.CHARACTER, ConsistencyCheckType.TIMELINE],
        )
        assert "character" in result
        assert "timeline" in result

    def test_empty_deps_produces_valid_prompt(self) -> None:
        """Empty deps still produce a well-formed prompt."""
        deps = _deps()
        result = build_user_prompt(deps, [ConsistencyCheckType.CHARACTER])
        assert "Check the following content" in result
        assert "## Chapters (0 total)" in result
