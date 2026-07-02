"""ADR-062 P3 — doc↔status-SSOT consistency checker.

Single responsibility (RULE-06): scan derived status surfaces (CURRENT_STATE,
``docs/features/INDEX.md``, feature specs) for status claims about governed
subjects and flag contradictions — either between two derived docs or between
a derived doc and the authoritative SSOT status declared in the vocabulary.

RULE-07: reads only the supplied doc texts (strings) and the vocabulary; imports
NO application runtime modules and performs NO filesystem access itself (the
caller resolves which docs to scan).

Mechanism:
  * A *claim* is a line in which a governed subject co-occurs with a recognized
    status term (high precision — only governed subjects + known vocabulary).
  * Each claim's raw term is normalized to a canonical token via the vocabulary.
  * For each subject, every pair of tokens (across docs and including the
    authoritative SSOT status) is tested against the contradiction table.
  * An explicit allowlist can suppress a subject's contradictions during the
    WARNING-only phase.

WARNING-only this cycle (exit 0): contradictions are reported but never fail
the gate. P3 ratchets to blocking in a follow-up once the baseline is clean.

ADR: docs/architecture/decisions/ADR-062-governance-drift-phase2-status-ssot.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from governance._status_vocab import StatusVocabulary, normalize_key

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "StatusClaim",
    "StatusConsistencyReport",
    "StatusContradiction",
    "check_status_consistency",
    "extract_claims",
    "scan_repo_docs",
]


@dataclass(frozen=True)
class StatusClaim:
    """A status claim extracted from a derived doc about a governed subject."""

    subject: str
    status: str  # canonical token
    doc: str  # doc identifier/path passed by the caller
    line: int
    text: str


@dataclass(frozen=True)
class StatusContradiction:
    """A contradiction found for one subject across claims/SSOT."""

    subject: str
    statuses: tuple[str, str]
    docs: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class StatusConsistencyReport:
    """Aggregated WARNING-only status-consistency report."""

    contradictions: tuple[StatusContradiction, ...] = field(default_factory=tuple)
    claims_scanned: int = 0

    @property
    def has_contradictions(self) -> bool:
        """True when any contradiction was found."""
        return bool(self.contradictions)


#: A word-boundary regex is built per subject to avoid substring matches like
#: ``not_character_voice``. Built lazily from the vocabulary's subjects.
def _subject_pattern(subject: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(subject) + r"(?![A-Za-z0-9_])")


def extract_claims(
    text: str,
    doc: str,
    vocab: StatusVocabulary,
) -> list[StatusClaim]:
    """Extract governed-subject status claims from *text*.

    A line yields a claim when it mentions a governed subject AND contains a
    recognized status phrase. Only the first canonical token per (subject,
    line) is recorded to avoid double-counting within one line.
    """
    claims: list[StatusClaim] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for subject in vocab.subjects:
            if not _subject_pattern(subject).search(line):
                continue
            token = _first_token(line, vocab)
            if token is not None:
                claims.append(
                    StatusClaim(
                        subject=subject,
                        status=token,
                        doc=doc,
                        line=line_no,
                        text=line.strip(),
                    )
                )
    return claims


def _first_token(line: str, vocab: StatusVocabulary) -> str | None:
    """Return the first canonical status token found in *line*, or ``None``.

    The line is normalized the same way vocabulary phrases are (lowercase,
    separators→space) so ``runtime-verified`` / ``runtime verified`` /
    ``runtime_verified`` all match the same key. Phrases are checked
    longest-first and with word boundaries so multi-word phrases win over
    single words and ``stable`` does not match ``stability``.
    """
    norm = normalize_key(line)
    for phrase in sorted(vocab.lookup, key=len, reverse=True):
        if not phrase:
            continue
        if _phrase_in(norm, phrase):
            return vocab.lookup[phrase]
    return None


def _phrase_in(norm_line: str, phrase: str) -> bool:
    """Word-boundary substring test of a space-normalized *phrase*."""
    pieces = [re.escape(p) for p in phrase.split() if p]
    if not pieces:
        return False
    pattern = re.compile(r"(?<![a-z0-9])" + r"\s+".join(pieces) + r"(?![a-z0-9])")
    return pattern.search(norm_line) is not None


def check_status_consistency(
    docs: dict[str, str],
    vocab: StatusVocabulary,
    *,
    allowlist_subjects: frozenset[str] | None = None,
) -> StatusConsistencyReport:
    """Reconcile status claims across *docs* and the authoritative SSOT.

    Args:
        docs: mapping of doc identifier -> doc text to scan.
        vocab: the loaded status vocabulary (subjects carry the SSOT status).
        allowlist_subjects: subjects whose contradictions are suppressed this
            cycle (WARNING-only baseline). Defaults to none.

    Returns:
        A :class:`StatusConsistencyReport` with detected contradictions.
    """
    suppressed = allowlist_subjects or frozenset()

    claims_by_subject: dict[str, list[StatusClaim]] = {s: [] for s in vocab.subjects}
    total_claims = 0
    for doc, text in docs.items():
        for claim in extract_claims(text, doc, vocab):
            claims_by_subject.setdefault(claim.subject, []).append(claim)
            total_claims += 1

    contradictions: list[StatusContradiction] = []
    for subject, claims in claims_by_subject.items():
        tokens = {c.status for c in claims}
        # Include the authoritative SSOT status as a reconciliation anchor.
        ssot = vocab.subjects.get(subject)
        if ssot:
            tokens.add(ssot)

        pair = _contradictory_pair(tokens, vocab)
        if pair is not None and subject not in suppressed:
            docs_seen = tuple(dict.fromkeys(c.doc for c in claims))
            contradictions.append(
                StatusContradiction(
                    subject=subject,
                    statuses=pair,
                    docs=docs_seen,
                    reason=(f"status surfaces disagree about '{subject}': {pair[0]} vs {pair[1]}"),
                )
            )

    return StatusConsistencyReport(
        contradictions=tuple(contradictions),
        claims_scanned=total_claims,
    )


def _contradictory_pair(
    tokens: set[str],
    vocab: StatusVocabulary,
) -> tuple[str, str] | None:
    """Return any contradictory token pair in *tokens*, or ``None``."""
    ordered = sorted(tokens)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            if vocab.contradicts(a, b):
                return (a, b)
    return None


def scan_repo_docs(
    repo_root: Path,
    vocab: StatusVocabulary,
) -> dict[str, str]:
    """Read the derived status surfaces under *repo_root* into a doc map.

    Scans ``docs/_shared/CURRENT_STATE.md``, ``docs/features/INDEX.md`` and the
    feature spec markdown under ``docs/features/``. Missing files are skipped
    (a missing surface is not a contradiction).
    """
    docs: dict[str, str] = {}
    candidates = [
        repo_root / "docs" / "_shared" / "CURRENT_STATE.md",
        repo_root / "docs" / "features" / "INDEX.md",
    ]
    for path in candidates:
        if path.is_file():
            docs[str(path.relative_to(repo_root))] = path.read_text(encoding="utf-8")
    features_dir = repo_root / "docs" / "features"
    if features_dir.is_dir():
        for path in sorted(features_dir.rglob("*.md")):
            if path.name == "INDEX.md":
                continue
            docs[str(path.relative_to(repo_root))] = path.read_text(encoding="utf-8")
    return docs
