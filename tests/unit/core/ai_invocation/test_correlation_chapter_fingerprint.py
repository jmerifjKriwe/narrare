"""Tests for fingerprint_chapter_texts (C2 — drift-persistence staleness).

Pins the ADR-045 scheme reuse: the digest is exactly ``_hash_payload`` over a
kind-discriminated payload (no new hash scheme), deterministic for identical
ordered input, order-sensitive, and valid for the empty band.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.ai_invocation.correlation import (
    _hash_payload,
    fingerprint_chapter_texts,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class TestFingerprintChapterTexts:
    def test_deterministic_for_same_ordered_inputs(self) -> None:
        texts: Sequence[str] = ["Alpha prose.", "Beta prose.", "Gamma prose."]

        assert fingerprint_chapter_texts(texts) == fingerprint_chapter_texts(list(texts))

    def test_order_sensitive(self) -> None:
        """Chapter order is load-bearing (list_by_novel position order)."""
        first = fingerprint_chapter_texts(["Alpha.", "Beta."])
        second = fingerprint_chapter_texts(["Beta.", "Alpha."])

        assert first != second

    def test_content_sensitive(self) -> None:
        assert fingerprint_chapter_texts(["One."]) != fingerprint_chapter_texts(["One. Edited."])

    def test_empty_list_is_valid_and_stable(self) -> None:
        assert fingerprint_chapter_texts([]) == fingerprint_chapter_texts([])

    def test_reuses_adr045_hash_payload_scheme(self) -> None:
        """The digest IS _hash_payload over the kind-discriminated payload —
        the ADR-045 correlation scheme, applied to a new payload shape."""
        digest = fingerprint_chapter_texts(["Alpha.", "Beta."])

        expected = _hash_payload(
            {
                "kind": "series_drift_chapter_texts",
                "chapter_texts": ["Alpha.", "Beta."],
            }
        )
        assert digest == expected

    def test_kind_discriminator_separates_domains(self) -> None:
        """A drift digest never equals a bare payload digest of the same texts
        (no accidental cross-context collision)."""
        texts = ["Alpha.", "Beta."]

        assert fingerprint_chapter_texts(texts) != _hash_payload(list(texts))

    def test_digest_is_64_hex_chars(self) -> None:
        digest = fingerprint_chapter_texts(["Alpha."])

        assert len(digest) == 64
        int(digest, 16)  # hex-decodable
