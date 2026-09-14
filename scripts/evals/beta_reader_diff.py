"""Diff reports for the beta-reader eval instrument (``--diff RUN_A RUN_B``).

Spec: ``docs/superpowers/specs/2026-09-14-beta-reader-eval-design.md`` — §6
(D4, before/after convention) and §9 Slice 3. Renders ``diff_report.md`` per
chapter x mode — prompt byte deltas, a Layer-1 violation table A|B,
count/severity/score deltas, and artifact pointers for side-by-side reading.
Pure local JSON/markdown munging over prior run trees — zero LLM calls.

RULE-04 note: split out of ``beta_reader_artifacts.py`` (run-tree rendering)
because the combined module exceeded the 600-line script hard limit;
modularize instead of compressing. Output lands in
``<runs-root>/diff-<RUN_A>-vs-<RUN_B>/diff_report.md`` (atomic write; the
runs root is gitignored, diffs are regenerable — no loud-collision rule).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from scripts.evals.beta_reader_artifacts import ArtifactError, phase_metrics
from scripts.evals.beta_reader_runner import PHASE1_MODE, PHASE2_MODE

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

__all__ = ["render_and_write_diff", "render_diff_report"]


@dataclass(frozen=True, slots=True)
class _CaseData:
    """Projected case data for diffing (prompts + optional scoring)."""

    prompt_bytes: dict[str, int]
    violations: dict[str, str] | None
    metrics: dict[str, int] | None


def render_and_write_diff(out_root: Path, run_a: str, run_b: str) -> Path:
    """Render ``RUN_A vs RUN_B`` and write ``diff_report.md`` atomically."""
    report = render_diff_report(out_root, run_a, run_b)
    diff_dir = out_root / f"diff-{run_a}-vs-{run_b}"
    diff_dir.mkdir(parents=True, exist_ok=True)
    target = diff_dir / "diff_report.md"
    _atomic_write(target, report)
    return target


def render_diff_report(runs_root: Path, run_a: str, run_b: str) -> str:
    """Per chapter x mode diff: prompt byte deltas, Layer-1 table, metric deltas."""
    data_a = _load_run(runs_root, run_a)
    data_b = _load_run(runs_root, run_b)
    lines = [
        f"# Eval Diff — {run_a} vs {run_b}",
        "",
        "Rendered from local run artifacts — zero LLM calls.",
        "",
    ]
    for mode in (PHASE1_MODE, PHASE2_MODE):
        for stem in sorted(set(data_a) | set(data_b)):
            lines += _diff_case_lines(run_a, run_b, data_a, data_b, stem, mode)
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    """Write via temp file + rename — a reader never sees a partial file."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _load_run(runs_root: Path, run_id: str) -> dict[str, dict[str, _CaseData]]:
    run_dir = runs_root / run_id
    if not (run_dir / "manifest.json").is_file():
        raise ArtifactError(f"run {run_id!r} not found under {runs_root} (missing manifest.json)")
    cases: dict[str, dict[str, _CaseData]] = {}
    for case_dir in sorted(run_dir.iterdir()):
        if not case_dir.is_dir() or "__" not in case_dir.name:
            continue
        stem, _, mode = case_dir.name.partition("__")
        cases.setdefault(stem, {})[mode] = _load_case_data(case_dir, run_id)
    return cases


def _load_case_data(case_dir: Path, run_id: str) -> _CaseData:
    system = case_dir / "system_prompt.txt"
    user = case_dir / "user_prompt.txt"
    if not system.is_file() or not user.is_file():
        raise ArtifactError(f"run {run_id!r}: {case_dir.name} is missing prompt artifacts")
    prompt_bytes = {"system": len(system.read_bytes()), "user": len(user.read_bytes())}
    layer1_path = case_dir / "layer1.json"
    response_path = case_dir / "response.json"
    if not layer1_path.is_file() or not response_path.is_file():
        return _CaseData(prompt_bytes=prompt_bytes, violations=None, metrics=None)  # dry run
    layer1 = cast("dict[str, object]", json.loads(layer1_path.read_text(encoding="utf-8")))
    response = cast("dict[str, object]", json.loads(response_path.read_text(encoding="utf-8")))
    rows = cast("list[dict[str, object]]", layer1["violations"])
    _, _, mode = case_dir.name.partition("__")
    return _CaseData(
        prompt_bytes=prompt_bytes,
        violations={str(row["check_id"]): str(row["detail"]) for row in rows},
        metrics=phase_metrics(mode, response),
    )


def _diff_case_lines(
    run_a: str,
    run_b: str,
    data_a: Mapping[str, Mapping[str, _CaseData]],
    data_b: Mapping[str, Mapping[str, _CaseData]],
    stem: str,
    mode: str,
) -> list[str]:
    case_a = data_a.get(stem, {}).get(mode)
    case_b = data_b.get(stem, {}).get(mode)
    header = [f"## {stem} x {mode}", ""]
    if case_a is None or case_b is None:
        missing = "run-a" if case_a is None else "run-b"
        return [*header, f"missing in {missing}", ""]
    lines = [
        *header,
        f"Artifacts: A `{run_a}/{stem}__{mode}/` · B `{run_b}/{stem}__{mode}/`",
        "",
        *_prompt_table(case_a, case_b),
    ]
    lines += _violations_table(case_a, case_b)
    lines += _metrics_table(case_a, case_b)
    return lines


def _table(header: str, alignment: str, rows: list[str], empty_note: str | None) -> list[str]:
    """One markdown table block; ``empty_note`` replaces rows when empty."""
    lines = [header, alignment, *rows]
    if not rows and empty_note:
        lines.append(empty_note)
    return [*lines, ""]


def _prompt_table(a: _CaseData, b: _CaseData) -> list[str]:
    rows = [
        f"| {name} | {a.prompt_bytes[name]} | {b.prompt_bytes[name]} "
        f"| {b.prompt_bytes[name] - a.prompt_bytes[name]:+d} |"
        for name in ("system", "user")
    ]
    return _table("| prompt | bytes A | bytes B | Δ |", "|---|---:|---:|---:|", rows, None)


def _violations_table(a: _CaseData, b: _CaseData) -> list[str]:
    if a.violations is None or b.violations is None:
        return ["Layer-1: n/a (dry run — no model output)", ""]
    check_ids = sorted(set(a.violations) | set(b.violations))
    rows = [
        f"| {check_id} | {a.violations.get(check_id, '(none)')} "
        f"| {b.violations.get(check_id, '(none)')} |"
        for check_id in check_ids
    ]
    return _table("| check_id | A | B |", "|---|---|---|", rows, "_no violations on either side_")


def _metrics_table(a: _CaseData, b: _CaseData) -> list[str]:
    if a.metrics is None or b.metrics is None:
        return ["Metrics: n/a (dry run — no model output)", ""]
    keys = sorted(set(a.metrics) | set(b.metrics))
    rows = [
        f"| {key} | {a.metrics.get(key, 0)} | {b.metrics.get(key, 0)} "
        f"| {b.metrics.get(key, 0) - a.metrics.get(key, 0):+d} |"
        for key in keys
    ]
    return _table("| metric | A | B | Δ |", "|---|---:|---:|---:|", rows, None)
