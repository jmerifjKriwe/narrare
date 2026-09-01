"""Typed inputs and outputs of the run-artifacts writer (plan Task 14).

The runner (Task 15) assembles one frozen ``RunInputs`` per run — the
three scorer records (Tasks 11-13), one ``CapabilityAnswer`` per driven
capability, the run's sanitized raw events (``benchmark.ingest_events``),
the stack facts, and the run identity — and hands it to
``benchmark.artifacts.write_run_artifacts``. Everything the writer needs
is data: clocks are the caller's ``started_at``/``finished_at`` values,
the git commit and image digests are injected (git via a provider
argument, digests as data gathered by the runner's stack manager), so
the writer stays testable without subprocesses or docker.

``CapabilityAnswer.__post_init__`` mirrors the ``CapabilityResult``
contract: OK results carry no reason, SKIPPED/ERROR results REQUIRE one
(an answer without its reason would silently hide a skipped surface).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from benchmark.drivers.base import CapabilityStatus

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from benchmark.config_schemas import BenchmarkConfig
    from benchmark.ingest_events import IngestEvent
    from benchmark.scoring.detection_records import DetectionReport
    from benchmark.scoring.retrieval_records import RetrievalScore
    from benchmark.scoring.score_records import BuildQualityScore

__all__ = [
    "ArtifactError",
    "ArtifactPaths",
    "CapabilityAnswer",
    "RunInputs",
    "StackFacts",
]


class ArtifactError(ValueError):
    """A run-artifact input violates its shape; fail loudly, write nothing."""


@dataclass(frozen=True)
class CapabilityAnswer:
    """One driven capability's answer row (answers.jsonl).

    ``parsed`` is the driver's parsed record (``CapabilityResult.parsed``)
    or ``None``; the writer projects it JSON-safely — the full raw payload
    stays in the run's event sink.
    """

    cap_id: str
    status: CapabilityStatus
    elapsed_seconds: float
    reason: str | None = None
    parsed: object = None

    def __post_init__(self) -> None:
        if not self.cap_id:
            raise ArtifactError("cap_id must be a non-empty capability id")
        if self.status is CapabilityStatus.OK and self.reason is not None:
            raise ArtifactError(f"{self.cap_id}: OK answers must not carry a reason")
        if self.status is not CapabilityStatus.OK and not self.reason:
            raise ArtifactError(f"{self.cap_id}: {self.status.value} answers must carry a reason")


@dataclass(frozen=True)
class StackFacts:
    """Stack identity facts for the manifest (gathered by the runner).

    ``image_digests`` is key-sorted tuple pairs for deterministic
    equality; ``api_version`` is the JSON-safe payload of the API's
    version endpoint. The pairs slot is mode-dependent (PO ruling):
    containers mode records per-service repository digests; hybrid mode
    has NO app image and records runtime identity instead — ``mode``,
    ``uvicorn_pid``, ``api_port`` (see ``benchmark.stack_hybrid``).
    """

    compose_sha256: str
    image_digests: tuple[tuple[str, str], ...]
    api_version: dict[str, object]


@dataclass(frozen=True)
class RunInputs:
    """Everything one run's artifact tree is rendered from (all required).

    ``fp_baseline`` records whether a clean-run FP baseline was applied
    during detection scoring (plan Task 15 v1: ``False`` — the clean run
    is a separate full run and its reports are not supplied; the overview
    must state the case so FP counts are never misread as subtracted).
    """

    variant: str
    mode: str
    corpus_version: int
    started_at: datetime
    finished_at: datetime
    config: BenchmarkConfig
    build_quality: BuildQualityScore
    detection: DetectionReport
    retrieval: RetrievalScore
    answers: tuple[CapabilityAnswer, ...]
    events: tuple[IngestEvent, ...]
    stack: StackFacts
    fp_baseline: bool


@dataclass(frozen=True)
class ArtifactPaths:
    """Locations of one run's written artifacts (``run_dir == out/<run_id>``)."""

    run_id: str
    run_dir: Path
    results: Path
    answers: Path
    events: Path
    manifest: Path
    overview: Path
