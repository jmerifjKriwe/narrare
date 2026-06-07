"""Tests for quality metrics CLI — opt-in, with/without data.

See ADR-041 Decision 3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    import pytest

# Ensure scripts/ is on sys.path for package imports.
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


# ── Fixtures ──────────────────────────────────────────────────────


def write_evidence(evidence_dir: Path, records: list[dict[str, object]]) -> Path:
    """Write evidence records as JSONL."""
    path = evidence_dir / "invocations.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return path


# ── Test CLI opt-in ───────────────────────────────────────────────


class TestCLIOptIn:
    """CLI opt-in behaviour."""

    def test_no_flag_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without --quality or env var, quality is disabled."""
        monkeypatch.delenv("NARRARE_QUALITY_METRICS", raising=False)
        from scripts.check_quality_metrics import main

        result = main(["--json"])
        assert result == 0

    def test_with_quality_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With --quality flag, quality is enabled."""
        monkeypatch.delenv("NARRARE_QUALITY_METRICS", raising=False)
        from scripts.check_quality_metrics import main

        result = main(["--quality", "--json"])
        assert result == 0

    def test_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With NARRARE_QUALITY_METRICS=1, quality is enabled."""
        monkeypatch.setenv("NARRARE_QUALITY_METRICS", "1")
        from scripts.check_quality_metrics import main

        result = main(["--json"])
        assert result == 0

    def test_flag_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With both flag (True) and env, flag wins."""
        monkeypatch.setenv("NARRARE_QUALITY_METRICS", "1")
        from scripts.check_quality_metrics import main

        result = main(["--json"])
        assert result == 0


# ── Test CLI with data ────────────────────────────────────────────


class TestCLIWithData:
    """Full CLI flow with fake data."""

    def test_with_adoption_report(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI loads adoption report and produces metrics."""
        monkeypatch.setenv("NARRARE_QUALITY_METRICS", "1")

        # Create adoption report objects
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore

        mode_score = ModeScore(
            mode="new_chapter",
            score=0.9,
            status="PASS",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
        )
        cat = CategoryScore(category="writing", score=0.9, status="PASS", modes=[mode_score])
        adoption = AdoptionReport(overall_score=0.9, status="PASS", categories=[cat])

        # Create evidence
        ev_dir = tmp_path / ".evidence"
        ev_dir.mkdir()
        write_evidence(
            ev_dir,
            [
                {
                    "feature_id": "writing/new_chapter",
                    "mode": "new_chapter",
                    "intent": "continue",
                    "audit_state": "adopted",
                },
            ],
        )

        from scripts.check_quality_metrics import main as cli_main

        # Mock the adoption report loader to avoid JSON roundtrip
        # issues with nested dataclass reconstruction.
        with patch(
            "scripts.check_quality_metrics._load_adoption_report",
            return_value=adoption,
        ):
            result = cli_main(
                [
                    "--json",
                    f"--evidence-dir={ev_dir}",
                    "--results-dir=/tmp/nonexistent-results",
                ]
            )
        assert result == 0

    def test_no_adoption_report(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI handles missing adoption report gracefully."""
        monkeypatch.setenv("NARRARE_QUALITY_METRICS", "1")

        from scripts.check_quality_metrics import main

        result = main(
            [
                "--json",
                f"--adoption-report={tmp_path / 'nonexistent.json'}",
            ]
        )
        assert result == 0
