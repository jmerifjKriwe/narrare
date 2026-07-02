"""ADR-062 P3 — doc↔status-SSOT consistency checker tests.

The checker scans derived status surfaces for status claims about governed
subjects and flags contradictions (doc↔doc or doc↔authoritative-SSOT) using
the status vocabulary's contradiction table.

WARNING-only this cycle: the checker reports contradictions but never fails
the gate. These unit tests exercise the analysis function directly with
synthetic docs and assert which contradictions are detected.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance._status_consistency import (  # noqa: E402
    StatusConsistencyReport,
    check_status_consistency,
    extract_claims,
)

if TYPE_CHECKING:
    from governance._status_vocab import StatusVocabulary

_VOCAB_PATH = _PROJECT_ROOT / "docs" / "architecture" / "governance" / "status_vocabulary.yaml"


def _vocab() -> StatusVocabulary:
    from governance._status_vocab import load_status_vocabulary

    return load_status_vocabulary(_VOCAB_PATH)


# ---------------------------------------------------------------------------
# extract_claims — only governed subjects paired with known status terms
# ---------------------------------------------------------------------------


def test_extract_claim_pairs_subject_with_status_token() -> None:
    vocab = _vocab()
    claims = extract_claims(
        "character_voice runtime adoption is runtime-verified.",
        "docs/features/INDEX.md",
        vocab,
    )
    assert len(claims) == 1
    assert claims[0].subject == "character_voice"
    assert claims[0].status == "runtime_verified"


def test_extract_ignores_unknown_status_phrases() -> None:
    """A subject without a recognized status term yields no claim."""
    vocab = _vocab()
    claims = extract_claims("character_voice is flüchtig.", "docs/x.md", vocab)
    assert claims == []


def test_extract_ignores_non_governed_subjects() -> None:
    """Only governed subjects are reconciled (high precision)."""
    vocab = _vocab()
    claims = extract_claims("some_other_feature is governed debt.", "docs/x.md", vocab)
    assert claims == []


def test_bare_static_verified_is_not_a_claim() -> None:
    """Bare 'static verified' (no 'only') must not produce a static_only claim."""
    vocab = _vocab()
    claims = extract_claims("character_voice is static verified.", "docs/x.md", vocab)
    assert claims == []


# ---------------------------------------------------------------------------
# check_status_consistency — contradiction detection
# ---------------------------------------------------------------------------


def test_doc_vs_ssot_contradiction_is_flagged() -> None:
    """A derived doc contradicting the authoritative SSOT status is flagged.

    This is the closed class: ``character_voice`` is runtime-verified (SSOT)
    but a derived doc claims governed debt.
    """
    vocab = _vocab()
    docs = {"docs/features/INDEX.md": "character_voice = governed debt"}
    report = check_status_consistency(docs, vocab)

    assert len(report.contradictions) == 1
    c = report.contradictions[0]
    assert c.subject == "character_voice"
    assert set(c.statuses) == {"governed_debt", "runtime_verified"}


def test_doc_vs_doc_contradiction_is_flagged() -> None:
    """Two derived docs disagreeing about the same subject is flagged."""
    vocab = _vocab()
    docs = {
        "docs/a.md": "character_voice is runtime-verified",
        "docs/b.md": "character_voice is governed debt",
    }
    report = check_status_consistency(docs, vocab)

    assert len(report.contradictions) == 1
    assert report.contradictions[0].subject == "character_voice"


def test_consistent_claims_produce_no_contradiction() -> None:
    """All docs + SSOT agree → clean report (the target baseline)."""
    vocab = _vocab()
    docs = {
        "docs/_shared/CURRENT_STATE.md": "character_voice is runtime-verified",
        "docs/features/INDEX.md": "character_voice runtime adoption is runtime-verified",
    }
    report = check_status_consistency(docs, vocab)
    assert report.contradictions == ()
    assert report.claims_scanned >= 2


def test_stable_and_runtime_verified_coexist_without_contradiction() -> None:
    """stable and runtime_verified are not a contradiction pair."""
    vocab = _vocab()
    docs = {
        "docs/a.md": "character_voice is runtime-verified",
        "docs/b.md": "character_voice Status -> stable",
    }
    report = check_status_consistency(docs, vocab)
    assert report.contradictions == ()


# ---------------------------------------------------------------------------
# Allowlist suppression
# ---------------------------------------------------------------------------


def test_allowlist_suppresses_a_contradiction() -> None:
    """An explicit allowlist entry suppresses a flagged contradiction."""
    vocab = _vocab()
    docs = {"docs/features/INDEX.md": "character_voice = governed debt"}
    report = check_status_consistency(docs, vocab, allowlist_subjects={"character_voice"})
    assert report.contradictions == ()


def test_allowlist_is_subject_specific() -> None:
    """Allowlisting one subject does not suppress another's contradiction."""
    vocab = _vocab()
    docs = {
        "docs/features/INDEX.md": "character_voice = governed debt\nvoice_check is governed debt"
    }
    report = check_status_consistency(docs, vocab, allowlist_subjects={"character_voice"})
    # character_voice suppressed; voice_check (ssot=adopted) still flagged.
    subjects = {c.subject for c in report.contradictions}
    assert subjects == {"voice_check"}


# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------


def test_report_records_scanned_claim_count() -> None:
    vocab = _vocab()
    docs = {
        "docs/a.md": "character_voice is runtime-verified\nvoice_check is adopted",
        "docs/b.md": "character_voice is stable",
    }
    report = check_status_consistency(docs, vocab)
    assert isinstance(report, StatusConsistencyReport)
    # 3 claims: a(character_voice), a(voice_check), b(character_voice).
    assert report.claims_scanned == 3
    assert report.contradictions == ()
