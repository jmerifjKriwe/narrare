"""Tests for embeddings/hash.py — compute_content_hash."""

from __future__ import annotations

import time

from narrare_core.embeddings.hash import compute_content_hash


class TestComputeContentHash:
    """SHA-256 content hash for dirty detection."""

    def test_identical_content_produces_identical_hash(self) -> None:
        content = "The Forest Spirit dwells in the ancient grove."
        assert compute_content_hash(content) == compute_content_hash(content)

    def test_different_content_produces_different_hash(self) -> None:
        hash_a = compute_content_hash("Alice went down the rabbit hole.")
        hash_b = compute_content_hash("Bob climbed the beanstalk.")
        assert hash_a != hash_b

    def test_empty_string_produces_valid_hash(self) -> None:
        result = compute_content_hash("")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest length

    def test_unicode_content_produces_valid_hash(self) -> None:
        """Non-ASCII characters (emoji, CJK, accented) hash correctly."""
        content = "日本語テスト 🎭 café résumé naïve"
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_very_long_content_completes_within_one_second(self) -> None:
        """Performance: hashing 1MB of text should complete in <1s."""
        content = "x" * 1_000_000  # ~1 MB
        start = time.monotonic()
        result = compute_content_hash(content)
        elapsed = time.monotonic() - start
        assert isinstance(result, str)
        assert len(result) == 64
        assert elapsed < 1.0, f"Hashing took {elapsed:.3f}s, expected <1s"

    def test_hash_output_is_hex_string(self) -> None:
        result = compute_content_hash("test content")
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_is_deterministic_across_calls(self) -> None:
        """Same input always produces same output (no randomness)."""
        content = "deterministic test"
        results = [compute_content_hash(content) for _ in range(10)]
        assert len(set(results)) == 1

    def test_single_character_produces_valid_hash(self) -> None:
        result = compute_content_hash("a")
        assert len(result) == 64
        # Known SHA-256 of "a" in UTF-8
        expected = "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
        assert result == expected

    def test_content_with_newlines_produces_valid_hash(self) -> None:
        content = "line one\nline two\r\nline three"
        result = compute_content_hash(content)
        assert len(result) == 64
