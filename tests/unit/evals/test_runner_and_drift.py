"""Unit tests for Pydantic Evals runner serialization and drift parsing."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from evals.runner import run_suites
from scripts.eval_drift.parser import parse_pydantic_eval_report

if TYPE_CHECKING:
    from pathlib import Path


def test_runner_writes_smoke_report(tmp_path: Path) -> None:
    exit_code = run_suites(
        suite="rewrite_selection",
        mode="smoke",
        results_dir=tmp_path,
        minimum_score=0.8,
        judge_model=None,
    )

    report_path = tmp_path / "rewrite_selection.json"
    assert exit_code == 0
    assert report_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["framework"] == "pydantic-evals"
    assert payload["cases"]


def test_runner_writes_staged_consistency_smoke_report(tmp_path: Path) -> None:
    exit_code = run_suites(
        suite="consistency_staged",
        mode="smoke",
        results_dir=tmp_path,
        minimum_score=0.8,
        judge_model=None,
    )

    report_path = tmp_path / "consistency_staged.json"
    assert exit_code == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "consistency_staged"
    assert [case["name"] for case in payload["cases"]] == [
        "stage1-extracts-temporal-and-object-facts",
        "stage2-detects-reversed-temporal-order",
        "e2e-detects-temporal-contradiction-without-cloak-false-positive",
    ]


def test_drift_parser_reads_pydantic_eval_report(tmp_path: Path) -> None:
    report_path = tmp_path / "suite.json"
    report_path.write_text(
        json.dumps(
            {
                "framework": "pydantic-evals",
                "cases": [
                    {"name": "case-a", "scores": {"Quality": 0.75}, "assertions": {}},
                    {"name": "case-b", "scores": {}, "assertions": {"Valid": True}},
                ],
            }
        ),
        encoding="utf-8",
    )

    parsed = parse_pydantic_eval_report(report_path)

    assert parsed.source == "suite"
    assert [case.name for case in parsed.test_cases] == ["case-a", "case-b"]
    assert parsed.test_cases[0].avg_score == 0.75
    assert parsed.test_cases[1].avg_score == 1.0
