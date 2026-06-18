#!/usr/bin/env python3
"""Evidence loading for adoption scoring.

Loads probe evidence from file-based JSONL or EvidenceRepository,
and preference enrichment marker files.

Extracted from scorer_modes.py to respect RULE-04 file size limits.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare.evidence.contracts import EvidenceRepository

_KNOWN_FEATURES: list[str] = [
    "writing",
    "analysis",
    "kb",
    "planning",
    "generation",
    "memory",
    "chat",
]

_PLACEHOLDER_STATES = {"identified", "static_verified", "static_only"}
_VALID_PREFERENCE_STATUSES = {"provided", "enriched", "available", "verified"}


def _feature_mode(record: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract feature/mode from a future-proof evidence record shape."""
    feature_id = record.get("feature_id") or record.get("feature")
    mode = record.get("mode") or record.get("feature_mode")
    return (str(feature_id) if feature_id else None, str(mode) if mode else None)


def _is_placeholder_record(record: dict[str, Any]) -> bool:
    """Return True for static-only/placeholder evidence records."""
    state = record.get("audit_state") or record.get("adoption_state") or record.get("current_state")
    if isinstance(state, str) and state in _PLACEHOLDER_STATES:
        return True
    if record.get("final_prompt_validated") is False:
        return True
    if record.get("preference_status") == "not_applicable":
        return True
    return "budget" in record and record.get("budget") is None


def _records_from_marker(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return structured records from a marker when present."""
    raw_records: object = data.get("records") or data.get("invocations") or []
    if not isinstance(raw_records, list):
        return []
    records: list[dict[str, Any]] = []
    for record in cast("list[object]", raw_records):
        if isinstance(record, dict):
            records.append(cast("dict[str, Any]", record))
    return records


def _modes_from_records(
    records: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, set[str]]:
    """Build feature->modes from records accepted by *predicate*."""
    result: dict[str, set[str]] = {}
    for record in records:
        feature_id, mode = _feature_mode(record)
        if feature_id and mode and predicate(record):
            result.setdefault(feature_id, set()).add(mode)
    return result


def _modes_from_legacy_features(data: dict[str, Any]) -> dict[str, set[str]]:
    """Read legacy marker ``features`` mapping used by current probe scripts."""
    features: object = data.get("features", {})
    if not isinstance(features, dict):
        return {}
    result: dict[str, set[str]] = {}
    for feature_id, modes in cast("dict[object, object]", features).items():
        if isinstance(modes, list):
            feature_key = str(feature_id)
            result[feature_key] = {str(mode) for mode in cast("list[object]", modes)}
    return result


def _load_marker_modes(
    marker_path: Path,
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, set[str]]:
    """Load marker modes, preferring structured ADR-045 records when present."""
    if not marker_path.exists():
        return {}
    try:
        with marker_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    records = _records_from_marker(cast("dict[str, Any]", data))
    if records:
        return _modes_from_records(records, predicate)
    return _modes_from_legacy_features(cast("dict[str, Any]", data))


def _load_from_repo(evidence_repo: EvidenceRepository) -> dict[str, set[str]]:
    """Load probe evidence from an EvidenceRepository.

    Calls ``get_distinct_modes()`` for each known feature and returns
    the same ``dict[str, set[str]]`` format as the file-based loader.

    Returns ``{}`` if the repo raises.
    """
    known = _KNOWN_FEATURES

    async def _query() -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for fid in known:
            modes = await evidence_repo.get_distinct_modes(fid)
            if modes:
                result[fid] = set(modes)
        return result

    try:
        return asyncio.run(_query())
    except Exception:
        return {}


def load_probe_evidence(
    evidence_dir: str | Path | None = None,
    evidence_repo: Any | None = None,
) -> dict[str, set[str]]:
    """Load probe evidence from file or repository.

    When *evidence_repo* is provided, queries the ``EvidenceRepository``
    for distinct modes per known feature.  Otherwise falls back to
    reading from ``invocations.jsonl`` under *evidence_dir*.

    Returns mapping: feature_id -> {mode1, mode2, ...}
    Returns empty dict if no evidence source is available.
    """
    if evidence_repo is not None:
        return _load_from_repo(evidence_repo)

    if evidence_dir is not None:
        evidence_file = Path(evidence_dir) / "invocations.jsonl"
        if not evidence_file.exists():
            return {}

        result: dict[str, set[str]] = {}
        with evidence_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _is_placeholder_record(record):
                    continue
                fid, mode = _feature_mode(record)
                if fid and mode:
                    result.setdefault(fid, set()).add(mode)
        return result

    return {}


def load_preference_enrichment_evidence(
    evidence_dir: str | Path,
) -> dict[str, set[str]]:
    """Load preference enrichment marker file.

    Reads marker from ``preference_enrichment_probe.py``.
    Returns ``{feature_id: {mode, ...}}`` or empty dict.
    """
    marker_path = Path(evidence_dir) / "preference_enrichment.json"
    return _load_marker_modes(
        marker_path,
        lambda record: (
            not _is_placeholder_record(record)
            and record.get("preference_status") in _VALID_PREFERENCE_STATUSES
        ),
    )


def load_final_validation_evidence(evidence_dir: str | Path) -> dict[str, set[str]]:
    """Load final validation marker file.

    Reads marker from ``validation_budget_probes.py``.
    Returns ``{feature_id: {mode, ...}}`` or empty dict.
    """
    marker_path = Path(evidence_dir) / "final_validation.json"
    return _load_marker_modes(
        marker_path,
        lambda record: (
            not _is_placeholder_record(record)
            and (
                record.get("final_prompt_validated") is True
                or record.get("validation_status") in {"passed", "verified"}
            )
        ),
    )


def load_budget_resolution_evidence(evidence_dir: str | Path) -> dict[str, set[str]]:
    """Load budget resolution marker file.

    Reads marker from ``validation_budget_probes.py``.
    Returns ``{feature_id: {mode, ...}}`` or empty dict.
    """
    marker_path = Path(evidence_dir) / "budget_resolution.json"
    return _load_marker_modes(
        marker_path,
        lambda record: (
            not _is_placeholder_record(record)
            and any(
                record.get(field) is not None
                for field in (
                    "budget",
                    "budget_decision",
                    "max_output_tokens",
                    "effective_output_tokens",
                )
            )
        ),
    )


def load_evidence_sink_evidence(evidence_dir: str | Path) -> dict[str, set[str]]:
    """Load evidence sink marker file.

    Reads evidence from ``evidence_sink.json``.
    Returns ``{feature_id: {mode, ...}}`` or empty dict.
    """
    marker_path = Path(evidence_dir) / "evidence_sink.json"
    return _load_marker_modes(
        marker_path,
        lambda record: not _is_placeholder_record(record),
    )
