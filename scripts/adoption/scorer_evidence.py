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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
                fid = record.get("feature_id")
                mode = record.get("mode")
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
    if not marker_path.exists():
        return {}
    try:
        with marker_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {fid: set(modes) for fid, modes in data.get("features", {}).items()}
    except json.JSONDecodeError, KeyError:
        return {}


def load_final_validation_evidence(evidence_dir: str | Path) -> dict[str, set[str]]:
    """Load final validation marker file.

    Reads marker from ``validation_budget_probes.py``.
    Returns ``{feature_id: {mode, ...}}`` or empty dict.
    """
    marker_path = Path(evidence_dir) / "final_validation.json"
    if not marker_path.exists():
        return {}
    try:
        with marker_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {fid: set(modes) for fid, modes in data.get("features", {}).items()}
    except json.JSONDecodeError, KeyError:
        return {}


def load_budget_resolution_evidence(evidence_dir: str | Path) -> dict[str, set[str]]:
    """Load budget resolution marker file.

    Reads marker from ``validation_budget_probes.py``.
    Returns ``{feature_id: {mode, ...}}`` or empty dict.
    """
    marker_path = Path(evidence_dir) / "budget_resolution.json"
    if not marker_path.exists():
        return {}
    try:
        with marker_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {fid: set(modes) for fid, modes in data.get("features", {}).items()}
    except json.JSONDecodeError, KeyError:
        return {}
