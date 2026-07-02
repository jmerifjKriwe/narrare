"""ADR-061 P1 — per-setting effect-integrity checker (presence AND truth).

Single responsibility (RULE-06): for every ``user`` / ``project`` / ``adopted``
matrix entry, verify that the ``runtime_consumer`` references a REAL code
location that consumes the resolved value, and that the cited evidence covers
THIS setting (not a sibling).

Closes RC1 (presence != truth): the matrix's old presence-based checker
(``configuration_matrix.validate_matrix``) only asserted the
``runtime_consumer`` string was non-empty. This module grounds the claim
against an evidence manifest that binds each ``setting_id`` to a real consumer
file + symbol and the named test that proves changing the value changes
behaviour. A plausible-looking lie (``WritingSessionHandler`` pointing at a file
that does not contain it) is now detectable.

Two verification strategies (per the ADR):
  * **graph** — verified against the code knowledge graph at authoring time
    (consumer symbol resolves and the resolved value reaches it).
  * **manifest** — the evidence-manifest fallback for indirect / DI / async
    consumers; the checker asserts the manifest entry exists AND the cited
    consumer file/symbol and test exist on disk.

WARNING-only this cycle (exit 0): unproven entries become governed debt
(ADR-056 true-debt semantics), reported but non-blocking. P1 ratchets to
blocking in a follow-up once the baseline is clean.

RULE-07: reads the manifest (YAML) and the cited source/test FILES (as text,
never imported). Imports no application runtime modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

import yaml

if TYPE_CHECKING:
    from pathlib import Path

    from governance._matrix_types import MatrixEntry

__all__ = [
    "EffectEvidenceEntry",
    "EffectIntegrityReport",
    "EffectVerificationDetail",
    "Verification",
    "load_effect_evidence",
    "validate_effect_integrity",
]

#: Classifications that are user/project-facing (always in P1 scope).
_EFFECTIVE_CLASSIFICATIONS: frozenset[str] = frozenset({"user", "project"})


class Verification(StrEnum):
    """How a setting's effect-integrity was proven (recorded in the manifest)."""

    GRAPH = "graph"
    MANIFEST = "manifest"


@dataclass(frozen=True)
class EffectEvidenceEntry:
    """One row of the per-setting effect-evidence manifest."""

    setting_id: str
    verification: Verification
    consumer_file: str
    consumer_symbol: str
    test_file: tuple[str, ...]
    notes: str | None = None


@dataclass(frozen=True)
class EffectVerificationDetail:
    """The verification outcome for a single in-scope matrix entry."""

    setting_id: str
    verified: bool
    verification: Verification | None
    reason: str


@dataclass(frozen=True)
class EffectIntegrityReport:
    """Aggregated WARNING-only effect-integrity report."""

    total_in_scope: int
    verified: int
    consumer_only: int
    gaps: int
    broken: int
    details: tuple[EffectVerificationDetail, ...] = field(default_factory=tuple)

    @property
    def has_governed_debt(self) -> bool:
        """True when any in-scope entry is not fully verified (debt or defect)."""
        return (self.total_in_scope - self.verified) > 0


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


def load_effect_evidence(
    path: Path,
) -> tuple[list[EffectEvidenceEntry], frozenset[str]]:
    """Load the effect-evidence manifest.

    Returns:
        (entries, composite_allowlist) — the per-setting evidence rows and the
        ADR-061 P2 approved-composite setting_ids (seeded empty).

    Raises:
        FileNotFoundError: if *path* does not exist.
        yaml.YAMLError: if the document is not valid YAML.
    """
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        msg = f"effect-evidence manifest root must be a mapping, got {type(data).__name__}"
        raise ValueError(msg)
    mapping = cast("dict[str, Any]", data)

    allowlist: frozenset[str] = _load_allowlist(mapping.get("composite_allowlist"))

    entries: list[EffectEvidenceEntry] = []
    raw_entries = mapping.get("entries", [])
    if isinstance(raw_entries, list):
        for raw in cast("list[object]", raw_entries):
            if isinstance(raw, dict):
                entries.append(_parse_evidence(cast("dict[str, Any]", raw)))
    return entries, allowlist


def _load_allowlist(raw: object) -> frozenset[str]:
    """Coerce the composite_allowlist field into a frozen set of ids."""
    if not isinstance(raw, list):
        return frozenset()
    items = cast("list[object]", raw)
    return frozenset(str(item).strip() for item in items if str(item).strip())


def _parse_evidence(raw: dict[str, Any]) -> EffectEvidenceEntry:
    """Coerce a raw manifest mapping into an :class:`EffectEvidenceEntry`."""
    verification_raw = str(raw.get("verification", "manifest")).strip().lower()
    try:
        verification = Verification(verification_raw)
    except ValueError:
        verification = Verification.MANIFEST

    test_file_raw = raw.get("test_file", ())
    if isinstance(test_file_raw, str):
        test_file: tuple[str, ...] = (test_file_raw,)
    elif isinstance(test_file_raw, list):
        items = cast("list[object]", test_file_raw)
        test_file = tuple(str(item).strip() for item in items if str(item).strip())
    else:
        test_file = ()

    return EffectEvidenceEntry(
        setting_id=str(raw.get("setting_id", "")),
        verification=verification,
        consumer_file=str(raw.get("consumer_file", "")),
        consumer_symbol=str(raw.get("consumer_symbol", "")),
        test_file=test_file,
        notes=_opt_str(raw.get("notes")),
    )


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def validate_effect_integrity(
    entries: list[MatrixEntry],
    evidence_by_sid: dict[str, EffectEvidenceEntry],
    repo_root: Path,
) -> EffectIntegrityReport:
    """Verify each in-scope entry against the evidence manifest.

    An entry is in P1 scope when ``classification`` is ``user``/``project`` OR
    ``lifecycle`` is ``adopted``. Each in-scope entry is classified:

    * **verified** — manifest entry exists, the consumer file exists, the
      consumer symbol is present in that file, and at least one cited test
      exists AND references the setting_id or consumer_symbol.
    * **consumer_only** — consumer is real but no cited test covers THIS
      setting (sibling-evidence gap; ADR-060 class).
    * **gap** — no manifest entry (governed debt).
    * **broken** — manifest entry cites a non-existent file/symbol (defect).
    """
    details: list[EffectVerificationDetail] = []
    verified = consumer_only = gaps = broken = 0

    for entry in entries:
        if not _in_p1_scope(entry):
            continue
        ev = evidence_by_sid.get(entry.setting_id)
        if ev is None:
            gaps += 1
            details.append(
                EffectVerificationDetail(
                    setting_id=entry.setting_id,
                    verified=False,
                    verification=None,
                    reason="no manifest entry — add an effect-evidence record (governed debt)",
                )
            )
            continue

        outcome = _verify_entry(entry, ev, repo_root)
        details.append(outcome.detail)
        if outcome.kind is _OutcomeKind.VERIFIED:
            verified += 1
        elif outcome.kind is _OutcomeKind.CONSUMER_ONLY:
            consumer_only += 1
        elif outcome.kind is _OutcomeKind.BROKEN:
            broken += 1

    total_in_scope = verified + consumer_only + gaps + broken
    return EffectIntegrityReport(
        total_in_scope=total_in_scope,
        verified=verified,
        consumer_only=consumer_only,
        gaps=gaps,
        broken=broken,
        details=tuple(details),
    )


def _in_p1_scope(entry: MatrixEntry) -> bool:
    """user/project classification OR adopted lifecycle (ADR-061 P1)."""
    return entry.classification in _EFFECTIVE_CLASSIFICATIONS or entry.lifecycle == "adopted"


class _OutcomeKind(StrEnum):
    VERIFIED = "verified"
    CONSUMER_ONLY = "consumer_only"
    BROKEN = "broken"


@dataclass(frozen=True)
class _Outcome:
    kind: _OutcomeKind
    detail: EffectVerificationDetail


def _verify_entry(
    entry: MatrixEntry,
    ev: EffectEvidenceEntry,
    repo_root: Path,
) -> _Outcome:
    """Ground-truth a single manifest entry against the filesystem."""
    consumer_path = repo_root / ev.consumer_file
    if not consumer_path.is_file():
        return _broken(entry, ev, f"consumer_file does not exist: {ev.consumer_file}")

    consumer_text = consumer_path.read_text(encoding="utf-8", errors="replace")
    if ev.consumer_symbol not in consumer_text:
        return _broken(
            entry,
            ev,
            f"consumer_symbol '{ev.consumer_symbol}' not found in {ev.consumer_file}",
        )

    # At least one cited test must exist AND reference THIS setting (not a sibling).
    covering_test = None
    missing_test = False
    for test_path_str in ev.test_file:
        test_path = repo_root / test_path_str
        if not test_path.is_file():
            missing_test = True
            continue
        test_text = test_path.read_text(encoding="utf-8", errors="replace")
        if entry.setting_id in test_text or ev.consumer_symbol in test_text:
            covering_test = test_path_str
            break

    if covering_test is None:
        if missing_test:
            return _broken(entry, ev, "no cited test_file exists on disk")
        # Consumer is real, but no cited test references this setting/consumer
        # — the ADR-060 sibling-evidence class.
        return _outcome(
            entry,
            ev,
            _OutcomeKind.CONSUMER_ONLY,
            "consumer verified but no cited test references this setting (sibling-evidence gap)",
        )

    return _outcome(
        entry,
        ev,
        _OutcomeKind.VERIFIED,
        f"consumer + test verified ({covering_test})",
    )


def _broken(entry: MatrixEntry, ev: EffectEvidenceEntry, reason: str) -> _Outcome:
    return _outcome(entry, ev, _OutcomeKind.BROKEN, reason)


def _outcome(
    entry: MatrixEntry,
    ev: EffectEvidenceEntry,
    kind: _OutcomeKind,
    reason: str,
) -> _Outcome:
    return _Outcome(
        kind=kind,
        detail=EffectVerificationDetail(
            setting_id=entry.setting_id,
            verified=kind is _OutcomeKind.VERIFIED,
            verification=ev.verification,
            reason=reason,
        ),
    )
