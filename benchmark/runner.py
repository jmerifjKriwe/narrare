"""The benchmark run orchestrator (plan Task 15).

One run = stack up → client → provision (user + LLM) → corpus → ingest
(build path, fills run targets) → drive capabilities → score (with its
own FULL KB-state fetch as the scoring prerequisite,
``benchmark.runner_scoring``) → artifacts → teardown. ALL of it sits in
try/finally so TEARDOWN ALWAYS RUNS (verified residue-free) unless
``keep_stack`` is set; a failure at any stage first writes the failure
artifacts (``runner_failure``), then re-raises AFTER teardown — a
partial run never leaves a stack behind and never leaves no evidence.

Binding v1 decisions (task brief riders):

- SERIES PROVISIONING: single-novel runs do NOT provision a series —
  ``targets`` never carries ``series_id``, so the series-scoped check
  capabilities CAP-CHK-02/03 skip STRUCTURALLY via ``require_target``
  (honest ``SKIPPED(structural)`` rows in the artifacts, never a
  fabricated id). CAP-CHK-05 is NOT series-scoped — its structural
  target is the first ingested chapter (``drivers.check_direction_streams``
  docstring) — and IS driven; the brief's "CHK-02/03/05" grouping is
  flagged in the task report for a coordinator ruling.
- FP BASELINE: the clean run is a SEPARATE full run. Within one run NO
  clean baseline is supplied — detection is scored WITHOUT baseline
  subtraction (``clean_reports={}``) and ``RunInputs.fp_baseline=False``
  makes the overview state exactly that.
- CLEAN VARIANT: no injected errors — detection is an EMPTY report (the
  clean run's check reports are FP-baseline material, not detection
  evidence; see ``runner_scoring``).
- PROVISION OUTCOME: deliberately unused — ingest creates its OWN fresh
  novel per run (run isolation, ``benchmark.ingest`` docstring); the
  wizard's novel is never reused.
- TIMING: the config template carries no timing section, so SSE/poll
  timings are pinned constants (``runner_driving``).

Failure while WRITING the failure artifacts: the write error propagates
chained (``__context__`` carries the ORIGINAL run error — the root cause
is never masked) and teardown still runs. Argument validation (unknown /
duplicate capability ids) happens BEFORE the stack is created: it raises
without artifacts and without a stack — nothing was started, so nothing
needs recording or tearing down.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from benchmark.artifacts import current_git_commit, write_run_artifacts
from benchmark.artifacts_records import ArtifactPaths, RunInputs
from benchmark.client import BenchmarkClient
from benchmark.corpus_loader import Corpus, load_corpus
from benchmark.drivers import driver_for
from benchmark.ingest import IngestResult, ingest
from benchmark.provision import ProvisionOutcome, provision
from benchmark.runner_driving import drive_capabilities, selected_capabilities
from benchmark.runner_failure import RunFailure, write_failure_artifacts
from benchmark.runner_scoring import fetch_scored_kb, score_run
from benchmark.runner_stackfacts import stack_facts
from benchmark.runner_targets import build_targets
from benchmark.stack import StackManager

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from benchmark.config_schemas import BenchmarkConfig
    from benchmark.corpus_loader import Corpus
    from benchmark.corpus_views import Chapter
    from benchmark.drivers.base import CapabilityDriver
    from benchmark.ingest_events import IngestEvent
    from benchmark.runner_scoring import ScoredKb

__all__ = [
    "CORPUS_ROOT",
    "DEFAULT_OUT_DIR",
    "ArtifactWriter",
    "FailureWriter",
    "IngestFn",
    "ProvisionFn",
    "RunRequest",
    "RunStack",
    "RunnerDeps",
    "ScoredKbFetcher",
    "default_driver_for",
    "run",
    "utc_now",
]

CORPUS_ROOT: Final[Path] = Path(__file__).resolve().parent / "corpus"
"""The committed benchmark corpus (loaded per run)."""

DEFAULT_OUT_DIR: Final[Path] = Path(__file__).resolve().parent / "runs"
"""Default artifact root (``benchmark/runs``, gitignored)."""


# ---------------------------------------------------------------------------
# Seams (production wiring lives in ``RunnerDeps`` defaults; tests fake these)
# ---------------------------------------------------------------------------


class RunStack(Protocol):
    """The stack seam: bring up, tear down verified, report identity facts."""

    def up(self) -> str: ...
    def teardown(self, *, verify: bool) -> None: ...
    def facts(self) -> tuple[str, tuple[tuple[str, str], ...]]: ...


class ProvisionFn(Protocol):
    """The provisioning seam (``benchmark.provision.provision``)."""

    def __call__(self, client: BenchmarkClient, config: BenchmarkConfig) -> ProvisionOutcome: ...


class IngestFn(Protocol):
    """The build-path seam (``benchmark.ingest.ingest``)."""

    def __call__(
        self,
        client: BenchmarkClient,
        chapters: Sequence[Chapter],
        *,
        variant: str,
        mode: str,
        events: list[IngestEvent],
        sleeper: Callable[[float], None],
    ) -> IngestResult: ...


class ArtifactWriter(Protocol):
    """The artifact seam (``benchmark.artifacts.write_run_artifacts``)."""

    def __call__(
        self, out_dir: Path, inputs: RunInputs, *, git_commit: Callable[[], str]
    ) -> ArtifactPaths: ...


class FailureWriter(Protocol):
    """The failure-artifact seam (``benchmark.runner_failure``)."""

    def __call__(
        self, out_dir: Path, failure: RunFailure, events: Sequence[IngestEvent]
    ) -> Path: ...


class ScoredKbFetcher(Protocol):
    """The scoring-prerequisite seam (``benchmark.runner_scoring.fetch_scored_kb``)."""

    def __call__(
        self,
        client: BenchmarkClient,
        corpus: Corpus,
        novel_id: str,
        chapter_ids: Mapping[str, str],
        config: BenchmarkConfig,
        events: list[IngestEvent],
        targets: Mapping[str, str],
    ) -> ScoredKb: ...


def _default_stack_factory(config: BenchmarkConfig) -> RunStack:
    return StackManager(config)


def _default_client_factory(base_url: str, timeout_seconds: float, origin: str) -> BenchmarkClient:
    return BenchmarkClient(base_url, timeout_seconds, origin=origin)


def default_driver_for(cap_id: str) -> CapabilityDriver:
    """Production driver provider: registry-resolved driver, instantiated."""
    return driver_for(cap_id)()


def utc_now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Request + dependency injection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunRequest:
    """One run's selection: variant/mode, output root, config, flags."""

    variant: str
    mode: str
    out_dir: Path
    config: BenchmarkConfig
    keep_stack: bool = False
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunnerDeps:
    """Every collaborator as an injectable seam (production defaults)."""

    stack_factory: Callable[[BenchmarkConfig], RunStack] = _default_stack_factory
    client_factory: Callable[[str, float, str], BenchmarkClient] = _default_client_factory
    provision_fn: ProvisionFn = provision
    load_corpus_fn: Callable[[Path], Corpus] = load_corpus
    ingest_fn: IngestFn = ingest
    driver_for_fn: Callable[[str], CapabilityDriver] = default_driver_for
    fetch_scored_kb_fn: ScoredKbFetcher = fetch_scored_kb
    write_artifacts_fn: ArtifactWriter = write_run_artifacts
    write_failure_fn: FailureWriter = write_failure_artifacts
    git_commit_fn: Callable[[], str] = current_git_commit
    clock: Callable[[], datetime] = utc_now
    ingest_sleeper: Callable[[float], None] = time.sleep
    corpus_root: Path = CORPUS_ROOT


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run(request: RunRequest, deps: RunnerDeps | None = None) -> ArtifactPaths:
    """Execute one benchmark run end to end (module docstring contract)."""
    deps = deps if deps is not None else RunnerDeps()
    selected = selected_capabilities(request.capabilities)
    started_at = deps.clock()
    stack = deps.stack_factory(request.config)
    events: list[IngestEvent] = []
    stage = "stack_up"
    try:
        base_url = stack.up()
        stage = "client"
        client = deps.client_factory(
            base_url, request.config.api.timeout_seconds, request.config.api.origin
        )
        try:
            stage = "provision"
            deps.provision_fn(client, request.config)
            stage = "corpus"
            corpus = deps.load_corpus_fn(deps.corpus_root)
            stage = "ingest"
            ingest_result = deps.ingest_fn(
                client,
                corpus.chapters(request.variant),
                variant=request.variant,
                mode=request.mode,
                events=events,
                sleeper=deps.ingest_sleeper,
            )
            stage = "driving"
            run_targets = build_targets(ingest_result)
            answers = drive_capabilities(
                client,
                corpus,
                ingest_result.novel_id,
                run_targets.chapter_ids,
                request.config,
                events,
                selected,
                deps.driver_for_fn,
                run_targets.targets,
            )
            stage = "scoring"
            # Scoring prerequisite: the FULL KB state is fetched HERE, not
            # taken from the driven answers — scoring has data no matter
            # which capabilities the user selected (runner_scoring docstring).
            scored_kb = deps.fetch_scored_kb_fn(
                client,
                corpus,
                novel_id=ingest_result.novel_id,
                chapter_ids=run_targets.chapter_ids,
                config=request.config,
                events=events,
                targets=run_targets.targets,
            )
            scores = score_run(corpus, request.variant, answers, run_targets.chapter_map, scored_kb)
            stage = "artifacts"
            inputs = RunInputs(
                variant=request.variant,
                mode=request.mode,
                corpus_version=corpus.version,
                started_at=started_at,
                finished_at=deps.clock(),
                config=request.config,
                build_quality=scores.build_quality,
                detection=scores.detection,
                retrieval=scores.retrieval,
                answers=answers,
                events=tuple(events),
                stack=stack_facts(stack, client),
                fp_baseline=False,
            )
            return deps.write_artifacts_fn(request.out_dir, inputs, git_commit=deps.git_commit_fn)
        finally:
            client.close()
    except Exception as error:
        _record_failure(request, deps, started_at, stage, events, error)
        raise
    finally:
        if not request.keep_stack:
            stack.teardown(verify=True)


def _record_failure(
    request: RunRequest,
    deps: RunnerDeps,
    started_at: datetime,
    stage: str,
    events: list[IngestEvent],
    error: Exception,
) -> None:
    """Write the failure artifacts; a write failure chains, never masks."""
    failure = RunFailure(
        variant=request.variant,
        mode=request.mode,
        started_at=started_at,
        failed_at=deps.clock(),
        stage=stage,
        error_type=type(error).__name__,
        error_message=str(error),
        keep_stack=request.keep_stack,
        event_count=len(events),
    )
    deps.write_failure_fn(request.out_dir, failure, tuple(events))
