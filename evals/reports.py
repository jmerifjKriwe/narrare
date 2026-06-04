"""Report serialization helpers for Pydantic Evals results."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path


def write_report_json(report: Any, path: Path, *, suite: str, mode: str) -> None:
    """Write a stable JSON summary of a Pydantic Evals report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "framework": "pydantic-evals",
        "suite": suite,
        "mode": mode,
        "report_name": getattr(report, "name", suite),
        "created_at": datetime.now(tz=UTC).isoformat(),
        "cases": [_case_summary(case) for case in getattr(report, "cases", [])],
        "failures": [_failure_summary(failure) for failure in getattr(report, "failures", [])],
        "rendered": report.render(include_input=True, include_output=True, include_durations=False),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _case_summary(case: Any) -> dict[str, Any]:
    scores = getattr(case, "scores", {})
    assertions = getattr(case, "assertions", {})
    return {
        "name": getattr(case, "name", "unknown"),
        "scores": {name: _result_value(value) for name, value in scores.items()},
        "assertions": {name: _result_value(value) for name, value in assertions.items()},
        "output": _jsonable(getattr(case, "output", None)),
    }


def _failure_summary(failure: Any) -> dict[str, str]:
    return {
        "name": str(getattr(failure, "name", "unknown")),
        "error_message": str(getattr(failure, "error_message", "")),
    }


def _result_value(result: Any) -> float | bool | str | None:
    value = getattr(result, "value", result)
    if isinstance(value, (float, bool, str)) or value is None:
        return value
    if isinstance(value, int):
        return float(value)
    return str(value)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        items = cast("list[object]", value)
        return [_jsonable(item) for item in items]
    if isinstance(value, dict):
        items = cast("dict[object, object]", value)
        return {str(key): _jsonable(item) for key, item in items.items()}
    return str(value)
