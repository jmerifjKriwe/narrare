"""Run-artifacts writer facade — one call, five deterministic files (Task 14).

``write_run_artifacts(out_dir, inputs)`` renders and writes the complete
artifact tree of one benchmark run into ``<out_dir>/<run_id>/``:

- ``results.json`` — per-capability x per-class scores + itemized lists
  (``benchmark.artifacts_json.results_document``);
- ``answers.jsonl`` — one JSON-safe projection line per driven capability;
- ``events.jsonl`` — the run's SANITIZED raw events, verbatim (the sink
  file; sanitization happened at ``record`` time);
- ``manifest.json`` — run id, timestamps, git commit, corpus version,
  config fingerprint (redacted-dict hash — NEVER raw secret values),
  stack facts, capability counters;
- ``overview.md`` — the human overview (``benchmark.artifacts_overview``).

Failure semantics: ALL content is rendered in memory BEFORE any file is
created — a validation or serialization failure leaves the runs root
untouched (no partial artifact trees). Each file is written through a
temporary file + ``os.replace`` (atomic per file). ``out_dir`` is created
if missing; a colliding run directory fails loudly (mkdir without
exist_ok). The run id's counter ``n`` derives from the runs-root listing
(``artifacts_json.next_run_id``) — deterministic, no global state.

External I/O seams: the git commit comes from the ``git_commit``
provider (default: ``subprocess git rev-parse HEAD`` — injectable in
tests); image digests and the API version payload arrive as data in
``inputs.stack`` (the runner's stack manager owns their providers).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess  # nosec B404 — fixed internal argv, no shell
from pathlib import Path
from typing import TYPE_CHECKING, Final

from benchmark.artifacts_json import (
    answers_lines,
    config_fingerprint,
    dumps_sorted,
    event_lines,
    manifest_document,
    next_run_id,
    results_document,
)
from benchmark.artifacts_overview import render_overview
from benchmark.artifacts_records import ArtifactError, ArtifactPaths, RunInputs

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
_GIT: Final[Path | str] = shutil.which("git") or "git"

_SHA256_HEX: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_SEGMENT: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

__all__ = [
    "ArtifactError",
    "ArtifactPaths",
    "RunInputs",
    "current_git_commit",
    "write_run_artifacts",
]


def current_git_commit() -> str:
    """Production git-commit provider: ``git rev-parse HEAD`` (no shell)."""
    completed = subprocess.run(  # noqa: S603  # nosec B603 — fixed internal argv, no shell
        [_GIT, "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ArtifactError(
            f"git rev-parse HEAD failed (rc={completed.returncode}): {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def write_run_artifacts(
    out_dir: Path,
    inputs: RunInputs,
    *,
    git_commit: Callable[[], str] = current_git_commit,
) -> ArtifactPaths:
    """Validate, render, and atomically write one run's artifact tree."""
    _validate(inputs)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = next_run_id(
        [entry.name for entry in out_dir.iterdir()],
        inputs.started_at.date().isoformat(),
        inputs.variant,
        inputs.mode,
    )
    fingerprint = config_fingerprint(inputs.config)
    commit = git_commit()
    payload = _render(inputs, run_id=run_id, git_commit=commit, fingerprint=fingerprint)
    run_dir = out_dir / run_id
    run_dir.mkdir()
    for name, content in payload.items():
        _atomic_write(run_dir / name, content)
    return ArtifactPaths(
        run_id=run_id,
        run_dir=run_dir,
        results=run_dir / "results.json",
        answers=run_dir / "answers.jsonl",
        events=run_dir / "events.jsonl",
        manifest=run_dir / "manifest.json",
        overview=run_dir / "overview.md",
    )


# ---------------------------------------------------------------------------
# Validation (fail loudly, write nothing)
# ---------------------------------------------------------------------------


def _validate(inputs: RunInputs) -> None:
    _segment("variant", inputs.variant)
    _segment("mode", inputs.mode)
    if inputs.corpus_version < 1:
        raise ArtifactError(f"corpus_version must be >= 1, got {inputs.corpus_version}")
    for name, moment in (("started_at", inputs.started_at), ("finished_at", inputs.finished_at)):
        if moment.tzinfo is None:
            raise ArtifactError(f"{name} must be timezone-aware, got {moment!r}")
    if inputs.finished_at < inputs.started_at:
        raise ArtifactError(
            f"finished_at {inputs.finished_at.isoformat()} is before "
            f"started_at {inputs.started_at.isoformat()}"
        )
    cap_ids = [answer.cap_id for answer in inputs.answers]
    if len(set(cap_ids)) != len(cap_ids):
        raise ArtifactError(f"cap_ids must be unique per run, got {cap_ids}")
    if not _SHA256_HEX.fullmatch(inputs.stack.compose_sha256):
        raise ArtifactError(
            f"compose_sha256 must be 64 lowercase hex chars, got {inputs.stack.compose_sha256!r}"
        )


def _segment(field: str, value: str) -> None:
    if not value or not _SEGMENT.fullmatch(value):
        raise ArtifactError(f"{field} {value!r} is not a safe non-empty path segment")


# ---------------------------------------------------------------------------
# Rendering + atomic writes
# ---------------------------------------------------------------------------


def _render(
    inputs: RunInputs,
    *,
    run_id: str,
    git_commit: str,
    fingerprint: dict[str, str],
) -> dict[str, str]:
    """Render ALL files in memory; any failure happens before a write."""
    return {
        "results.json": dumps_sorted(
            results_document(
                inputs.build_quality, inputs.detection, inputs.retrieval, inputs.resolution
            ),
            pretty=True,
        ),
        "answers.jsonl": "\n".join(answers_lines(inputs.answers)) + "\n" if inputs.answers else "",
        "events.jsonl": "\n".join(event_lines(inputs.events)) + "\n" if inputs.events else "",
        "manifest.json": dumps_sorted(
            manifest_document(inputs, run_id, git_commit),
            pretty=True,
        ),
        "overview.md": render_overview(
            inputs, run_id=run_id, git_commit=git_commit, fingerprint=fingerprint
        ),
    }


def _atomic_write(path: Path, content: str) -> None:
    """Write via temp file + rename — a reader never sees a partial file."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
