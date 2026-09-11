"""Partial-failure run artifacts (plan Task 15: "failure recorded").

A run that fails at ANY stage still leaves evidence: the runner builds a
frozen ``RunFailure`` (stage reached, error identity, timing, keep-stack
flag, event-sink size) and hands it to ``write_failure_artifacts``,
which atomically writes TWO files into ``<out>/<run-id>/``:

- ``failure.json`` — the structured error record;
- ``events.jsonl`` — the sanitized raw-event sink SO FAR, verbatim in
  the same format as complete runs (every HTTP exchange up to the
  failure — the ingest step contract guarantees the terminal event is
  always recorded before the error propagates).

Run id: ``<day>-<variant>-failed-<n>`` (the artifacts writer's
``next_run_id`` with ``mode="failed"``) — deterministic, no collision
with complete-run ids, and a subsequent complete run simply takes the
next counter. The writer renders everything in memory before any write
and writes through temp-file + rename (``benchmark.artifacts`` idiom);
a failure while WRITING the failure artifacts propagates chained with
the ORIGINAL error as ``__context__`` — the root cause is never masked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from benchmark.artifacts_json import dumps_sorted, event_lines, next_run_id

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from pathlib import Path

    from benchmark.ingest_events import IngestEvent

__all__ = ["RunFailure", "write_failure_artifacts"]


@dataclass(frozen=True)
class RunFailure:
    """The structured record of one failed run (failure.json)."""

    variant: str
    mode: str
    started_at: datetime
    failed_at: datetime
    stage: str
    error_type: str
    error_message: str
    keep_stack: bool
    event_count: int


def write_failure_artifacts(
    out_dir: Path, failure: RunFailure, events: Sequence[IngestEvent]
) -> Path:
    """Render + atomically write ``failure.json`` and ``events.jsonl``.

    Returns the run directory (``<out>/<run-id>``).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = next_run_id(
        [entry.name for entry in out_dir.iterdir()],
        failure.started_at.date().isoformat(),
        failure.variant,
        "failed",
    )
    run_dir = out_dir / run_id
    run_dir.mkdir()
    payload = {
        "run_id": run_id,
        "variant": failure.variant,
        "mode": failure.mode,
        "started_at": failure.started_at.isoformat(),
        "failed_at": failure.failed_at.isoformat(),
        "stage": failure.stage,
        "error": {"type": failure.error_type, "message": failure.error_message},
        "keep_stack": failure.keep_stack,
        "event_count": failure.event_count,
    }
    contents = {
        "failure.json": dumps_sorted(payload, pretty=True),
        "events.jsonl": "\n".join(event_lines(events)) + "\n" if events else "",
    }
    for name, content in contents.items():
        _atomic_write(run_dir / name, content)
    return run_dir


def _atomic_write(path: Path, content: str) -> None:
    """Write via temp file + rename — a reader never sees a partial file."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
