#!/usr/bin/env python3
"""Script-side evidence repository adapter for adoption checks.

ADR-045 Platform Phase 2 lets the standalone adoption checker exercise the
same repository-shaped evidence path as production without requiring an API
database session.  The adapter implements the minimal async method consumed by
``adoption.scorer_evidence._load_from_repo()`` and reads the local JSONL
evidence sink used by platform scripts.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from adoption.scorer_evidence import feature_mode, is_placeholder_record

if TYPE_CHECKING:
    from pathlib import Path


class ScriptEvidenceRepository:
    """Read invocation evidence from ``.evidence/invocations.jsonl``.

    This adapter intentionally implements only ``get_distinct_modes()`` because
    the adoption scorer's repository loader only needs that method.  It mirrors
    the file-based probe-evidence filtering so placeholder/static-only records
    cannot satisfy runtime adoption requirements.
    """

    def __init__(self, evidence_file: Path) -> None:
        self._evidence_file = evidence_file
        self._modes_by_feature: dict[str, set[str]] | None = None

    async def get_distinct_modes(self, feature_id: str) -> list[str]:
        """Return distinct non-placeholder modes recorded for ``feature_id``."""
        modes_by_feature = self._load_modes_by_feature()
        return sorted(modes_by_feature.get(feature_id, set()))

    def _load_modes_by_feature(self) -> dict[str, set[str]]:
        """Load and cache feature modes from the JSONL evidence sink."""
        if self._modes_by_feature is None:
            self._modes_by_feature = self._read_modes_by_feature()
        return self._modes_by_feature

    def _read_modes_by_feature(self) -> dict[str, set[str]]:
        """Read distinct modes while preserving scorer evidence semantics."""
        if not self._evidence_file.exists():
            return {}

        result: dict[str, set[str]] = {}
        with self._evidence_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(raw_record, dict):
                    continue
                record = cast("dict[str, Any]", raw_record)
                if is_placeholder_record(record):
                    continue
                feature, mode = feature_mode(record)
                if feature and mode:
                    result.setdefault(feature, set()).add(mode)
        return result
