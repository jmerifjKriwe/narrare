"""Tests for the script-side evidence repository adapter."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from adoption.script_evidence_repo import ScriptEvidenceRepository  # noqa: E402


def test_get_distinct_modes_filters_placeholder_records(tmp_path: Path) -> None:
    evidence_file = tmp_path / "invocations.jsonl"
    records = [
        {"feature_id": "writing", "mode": "new_chapter"},
        {"feature": "writing", "feature_mode": "continue_chapter"},
        {
            "feature_id": "writing",
            "mode": "static_placeholder",
            "audit_state": "static_verified",
        },
        {"feature_id": "analysis", "mode": "style"},
    ]
    evidence_file.write_text(
        "\n".join(json.dumps(record) for record in records) + "\nnot-json\n",
        encoding="utf-8",
    )
    repo = ScriptEvidenceRepository(evidence_file)

    modes = asyncio.run(repo.get_distinct_modes("writing"))

    assert modes == ["continue_chapter", "new_chapter"]


def test_get_distinct_modes_returns_empty_list_when_file_is_missing(tmp_path: Path) -> None:
    repo = ScriptEvidenceRepository(tmp_path / "missing.jsonl")

    modes = asyncio.run(repo.get_distinct_modes("writing"))

    assert modes == []
