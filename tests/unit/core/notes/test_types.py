"""Unit tests for narrare_core.notes.types — pure rules, no I/O (NOTES-001 §4)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.notes.types import (
    DEFAULT_NOTE_LIMITS,
    NoteLimits,
    NoteType,
    ScopeError,
    effective_title,
    fallback_title,
    normalize_tag,
    normalize_tags,
    validate_scope,
)


class TestNoteType:
    def test_note_type_keys_are_language_neutral(self) -> None:
        assert {t.value for t in NoteType} == {"idea", "concept", "question", "other"}

    def test_note_type_is_str_enum(self) -> None:
        assert NoteType.IDEA == "idea"
        assert isinstance(NoteType.OTHER, str)


class TestNoteLimits:
    def test_default_limits_match_spec_values(self) -> None:
        assert DEFAULT_NOTE_LIMITS.max_tags_per_note == 10
        assert DEFAULT_NOTE_LIMITS.max_tag_length == 32
        assert DEFAULT_NOTE_LIMITS.fallback_title_max_length == 200


class TestNormalizeTag:
    def test_lowercases_trims_and_collapses_whitespace(self) -> None:
        assert normalize_tag("  Plot   TWIST ") == "plot twist"

    def test_empty_tag_normalizes_to_empty(self) -> None:
        assert normalize_tag("   ") == ""


class TestNormalizeTags:
    def test_dedupes_case_insensitively_keeping_first_order(self) -> None:
        assert normalize_tags(["Plot", "plot", "  PLOT ", "world"]) == ["plot", "world"]

    def test_drops_empty_entries(self) -> None:
        assert normalize_tags(["", "   ", "real"]) == ["real"]

    def test_caps_tag_count_at_max(self) -> None:
        result = normalize_tags([f"t{i}" for i in range(DEFAULT_NOTE_LIMITS.max_tags_per_note + 5)])
        assert len(result) == DEFAULT_NOTE_LIMITS.max_tags_per_note
        assert result == [f"t{i}" for i in range(DEFAULT_NOTE_LIMITS.max_tags_per_note)]

    def test_clips_each_tag_to_max_length(self) -> None:
        assert len(normalize_tags(["x" * 100])[0]) == DEFAULT_NOTE_LIMITS.max_tag_length

    def test_custom_limits_override_tag_count_cap(self) -> None:
        limits = NoteLimits(max_tags_per_note=2)
        assert normalize_tags(["a", "b", "c"], limits=limits) == ["a", "b"]

    def test_custom_limits_override_tag_length_clip(self) -> None:
        limits = NoteLimits(max_tag_length=3)
        assert normalize_tags(["abcdefgh"], limits=limits) == ["abc"]


class TestFallbackTitle:
    def test_uses_first_non_empty_line(self) -> None:
        assert (
            fallback_title("\n\n  Twist: the aunt did it\nsecond line") == "Twist: the aunt did it"
        )

    def test_clips_to_max_length(self) -> None:
        assert len(fallback_title("x" * 500)) == 200

    def test_returns_empty_for_blank_content(self) -> None:
        assert fallback_title(" \n \n") == ""

    def test_custom_limits_override_clip_length(self) -> None:
        limits = NoteLimits(fallback_title_max_length=5)
        assert fallback_title("aufdermessersschneide", limits=limits) == "aufde"


class TestEffectiveTitle:
    def test_prefers_explicit_title(self) -> None:
        assert effective_title("  Named  ", "first line") == "Named"

    def test_blank_title_falls_back_to_content(self) -> None:
        assert effective_title("   ", "first line") == "first line"

    def test_none_title_falls_back_to_content(self) -> None:
        assert effective_title(None, "first line") == "first line"

    def test_custom_limits_thread_through_to_fallback(self) -> None:
        limits = NoteLimits(fallback_title_max_length=4)
        assert effective_title(None, "long content line", limits=limits) == "long"


class TestValidateScope:
    def test_both_none_is_global_and_valid(self) -> None:
        validate_scope(None, None)  # must not raise

    def test_one_link_is_valid(self) -> None:
        validate_scope(uuid4(), None)  # must not raise
        validate_scope(None, uuid4())  # must not raise

    def test_both_links_raise_scope_error(self) -> None:
        with pytest.raises(ScopeError, match="not both"):
            validate_scope(uuid4(), uuid4())
