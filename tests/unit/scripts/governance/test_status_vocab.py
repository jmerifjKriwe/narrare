"""ADR-062 P3 — status vocabulary loader tests.

The vocabulary is the reconciliation anchor for doc↔status-SSOT consistency.
These tests cover normalization, the contradiction table, governed subjects,
the allowlist, and that the real committed vocabulary parses cleanly.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance._status_vocab import (  # noqa: E402
    StatusVocabulary,
    load_status_vocabulary,
    normalize_status,
)

_VOCAB_PATH = _PROJECT_ROOT / "docs" / "architecture" / "governance" / "status_vocabulary.yaml"


# ---------------------------------------------------------------------------
# normalize_status — case/space/dash/backtick insensitive canonicalization
# ---------------------------------------------------------------------------


def test_normalize_maps_known_phrases_to_canonical_token() -> None:
    assert normalize_status("runtime-verified") == "runtime_verified"
    assert normalize_status("runtime verified") == "runtime_verified"
    assert normalize_status("governed debt") == "governed_debt"


def test_normalize_is_case_insensitive() -> None:
    assert normalize_status("Runtime-Verified") == "runtime_verified"
    assert normalize_status("GOVERNED DEBT") == "governed_debt"


def test_normalize_unknown_phrase_returns_none() -> None:
    """Unknown phrases are ignored (conservative precision guard)."""
    assert normalize_status("flüchtig") is None
    assert normalize_status("") is None


def test_bare_static_verified_is_not_mapped() -> None:
    """Bare 'static verified' (no 'only') must NOT map — progression is allowed."""
    assert normalize_status("static verified") is None
    assert normalize_status("static-verified-only") == "static_only"


# ---------------------------------------------------------------------------
# load_status_vocabulary — real committed vocabulary parses
# ---------------------------------------------------------------------------


def test_load_real_vocabulary_parses() -> None:
    vocab = load_status_vocabulary(_VOCAB_PATH)
    assert isinstance(vocab, StatusVocabulary)
    # Canonical tokens present.
    assert "runtime_verified" in vocab.canonical_tokens
    assert "governed_debt" in vocab.canonical_tokens


def test_real_vocabulary_has_conservative_contradiction_pairs() -> None:
    vocab = load_status_vocabulary(_VOCAB_PATH)
    # The ADR headline contradiction must be present.
    assert vocab.contradicts("runtime_verified", "governed_debt")
    assert vocab.contradicts("adopted", "governed_debt")
    assert vocab.contradicts("stable", "governed_debt")


def test_real_vocabulary_non_contradiction_pairs_are_false() -> None:
    vocab = load_status_vocabulary(_VOCAB_PATH)
    # stable and runtime_verified coexist (no contradiction).
    assert not vocab.contradicts("stable", "runtime_verified")
    assert not vocab.contradicts("adopted", "runtime_verified")


def test_real_vocabulary_has_governed_subjects_with_ssot_status() -> None:
    vocab = load_status_vocabulary(_VOCAB_PATH)
    assert "character_voice" in vocab.subjects
    assert vocab.subjects["character_voice"] == "runtime_verified"
    # ssot status must be a known canonical token.
    assert vocab.subjects["character_voice"] in vocab.canonical_tokens


def test_contradicts_is_symmetric() -> None:
    vocab = load_status_vocabulary(_VOCAB_PATH)
    assert vocab.contradicts("governed_debt", "runtime_verified") is True
    assert vocab.contradicts("runtime_verified", "governed_debt") is True
