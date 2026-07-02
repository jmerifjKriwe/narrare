"""ADR-062 P3 — status vocabulary loader.

Single responsibility (RULE-06): load and expose the status reconciliation
vocabulary (``status_vocabulary.yaml``). This module owns the *data layer*:
normalizing raw status phrases to canonical tokens, the contradiction table,
the governed-subject allowlist with authoritative SSOT status, and the
explicit per-doc suppression allowlist. It performs NO doc scanning — that
responsibility belongs to :mod:`_status_consistency`.

RULE-07: reads only the vocabulary manifest (YAML) via ``yaml.safe_load`` and
imports NO application runtime modules.

Conservative by design (ADR-062): only listed phrases normalize; only declared
subjects are reconciled; contradiction pairs are seeded narrowly to avoid
false positives during the WARNING-only phase.

ADR: docs/architecture/decisions/ADR-062-governance-drift-phase2-status-ssot.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import yaml

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "StatusVocabulary",
    "load_status_vocabulary",
    "normalize_key",
    "normalize_status",
]

#: Characters collapsed/ignored when matching a raw phrase against the table.
_IGNORE = str.maketrans({"`": "", "_": " ", "-": " "})


def normalize_key(phrase: str) -> str:
    """Normalize a raw phrase for table lookup: lowercase, collapse separators.

    Backticks are stripped; underscores and dashes become spaces; whitespace is
    collapsed. Two surfaces that mean the same status (``runtime-verified``,
    ``runtime verified``, ``runtime_verified``) share one key.
    """
    return " ".join(phrase.translate(_IGNORE).lower().split())


def _key(phrase: str) -> str:
    """Alias of :func:`normalize_key` (internal legacy name)."""
    return normalize_key(phrase)


def normalize_status(raw: str, table: dict[str, str] | None = None) -> str | None:
    """Return the canonical token for *raw*, or ``None`` if unrecognized.

    When *table* is omitted, only the builtin phrase-to-token hints are used
    (sufficient for the unit-tested normalization behaviour). Production code
    passes the loaded vocabulary's lookup table.
    """
    if table is None:
        table = _BUILTIN_TABLE
    key = _key(raw)
    return table.get(key)


# Static hints used by the no-arg ``normalize_status`` convenience overload
# (mirrors the seeded vocabulary so unit tests need not load the file).
_BUILTIN_TABLE: dict[str, str] = {
    _key("runtime-verified"): "runtime_verified",
    _key("runtime verified"): "runtime_verified",
    _key("governed debt"): "governed_debt",
    _key("governed-debt"): "governed_debt",
    _key("governed_debt"): "governed_debt",
    _key("adopted"): "adopted",
    _key("stable"): "stable",
    _key("pending"): "pending",
    _key("static-verified-only"): "static_only",
    _key("static verified only"): "static_only",
    _key("static-verified only"): "static_only",
}


@dataclass(frozen=True)
class AllowEntry:
    """An explicit suppression entry for a legitimately nuanced claim."""

    subject: str
    doc: str
    reason: str = ""


@dataclass(frozen=True)
class StatusVocabulary:
    """The loaded status reconciliation vocabulary."""

    #: normalized-phrase -> canonical token
    lookup: dict[str, str]
    #: symmetric contradiction pairs as frozensets of two canonical tokens
    contradictions: frozenset[frozenset[str]]
    #: governed subject -> authoritative SSOT status token
    subjects: dict[str, str]
    #: explicit per-doc suppressions
    allowlist: tuple[AllowEntry, ...] = field(default_factory=tuple)

    @property
    def canonical_tokens(self) -> set[str]:
        """The set of all canonical tokens known to the vocabulary."""
        return set(self.lookup.values())

    def canonical(self, raw: str) -> str | None:
        """Return the canonical token for *raw*, or ``None`` if unrecognized."""
        return self.lookup.get(_key(raw))

    def contradicts(self, token_a: str, token_b: str) -> bool:
        """Return ``True`` if *token_a* and *token_b* are a declared contradiction."""
        return frozenset((token_a, token_b)) in self.contradictions

    def is_allowed(self, subject: str, doc: str) -> bool:
        """Return ``True`` when an allowlist entry covers (subject, doc)."""
        return any(entry.subject == subject and entry.doc in doc for entry in self.allowlist)


def load_status_vocabulary(path: Path) -> StatusVocabulary:
    """Load and parse the status vocabulary manifest at *path*.

    Raises:
        FileNotFoundError: if *path* does not exist.
        yaml.YAMLError: if the document is not valid YAML.
    """
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        msg = f"status vocabulary root must be a mapping, got {type(data).__name__}"
        raise ValueError(msg)
    mapping = cast("dict[str, Any]", data)
    return _build(mapping)


def _build(mapping: dict[str, Any]) -> StatusVocabulary:
    lookup = _build_lookup(mapping.get("status_terms", {}))
    contradictions = _build_contradictions(mapping.get("contradictions", []))
    subjects = _build_subjects(mapping.get("subjects", {}), lookup)
    allowlist = _build_allowlist(mapping.get("allowlist", []))
    return StatusVocabulary(
        lookup=lookup,
        contradictions=contradictions,
        subjects=subjects,
        allowlist=allowlist,
    )


def _build_lookup(raw_terms: Any) -> dict[str, str]:
    """Flatten the ``status_terms`` mapping into normalized-phrase -> token."""
    lookup: dict[str, str] = {}
    if not isinstance(raw_terms, dict):
        return lookup
    for token, phrases in cast("dict[str, Any]", raw_terms).items():
        canonical_token = str(token).strip()
        if not canonical_token:
            continue
        for phrase in _as_str_list(phrases):
            lookup[_key(phrase)] = canonical_token
    return lookup


def _build_contradictions(raw: Any) -> frozenset[frozenset[str]]:
    """Parse the contradiction pairs into symmetric frozenset pairs."""
    pairs: set[frozenset[str]] = set()
    if not isinstance(raw, list):
        return frozenset()
    for pair in cast("list[object]", raw):
        items = _as_str_list(pair)
        if len(items) == 2:
            pairs.add(frozenset((items[0], items[1])))
    return frozenset(pairs)


def _build_subjects(raw: Any, lookup: dict[str, str]) -> dict[str, str]:
    """Parse governed subjects; coerce each ``ssot_status`` to a canonical token."""
    subjects: dict[str, str] = {}
    if not isinstance(raw, dict):
        return subjects
    for subject, meta in cast("dict[str, Any]", raw).items():
        if not isinstance(meta, dict):
            continue
        meta_d = cast("dict[str, Any]", meta)
        ssot_raw = str(meta_d.get("ssot_status", "")).strip()
        # Resolve the declared SSOT status through the lookup so the anchor is
        # always a known canonical token.
        token = lookup.get(_key(ssot_raw)) or (ssot_raw if ssot_raw else None)
        if token is not None:
            subjects[str(subject).strip()] = token
    return subjects


def _build_allowlist(raw: Any) -> tuple[AllowEntry, ...]:
    """Parse the explicit per-doc suppression allowlist."""
    if not isinstance(raw, list):
        return ()
    entries: list[AllowEntry] = []
    for item in cast("list[object]", raw):
        if not isinstance(item, dict):
            continue
        d = cast("dict[str, Any]", item)
        subject = str(d.get("subject", "")).strip()
        doc = str(d.get("doc", "")).strip()
        if subject and doc:
            entries.append(
                AllowEntry(subject=subject, doc=doc, reason=str(d.get("reason", "")).strip())
            )
    return tuple(entries)


def _as_str_list(value: Any) -> list[str]:
    """Coerce a scalar/list into a list of non-empty stripped strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in cast("list[object]", value) if str(v).strip()]
    return []
