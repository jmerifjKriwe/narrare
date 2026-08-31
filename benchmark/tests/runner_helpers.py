"""Fakes and fixtures for the runner wiring tests (plan Task 15).

ALL collaborators are faked at the runner's seams (no docker, no HTTP
beyond the client's scripted MockTransport answering only the runner's
own manifest fetch): the stack manager, provisioning, ingest, the
capability drivers, both artifact writers, the git provider, and the
clock. The corpus is a tiny REAL corpus on disk (exercising
``load_corpus`` wiring through the true loader). Parsed capability
records are REAL driver/scorer record types so the scoring stage runs
for real over scripted inputs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import httpx

from benchmark.artifacts_records import ArtifactPaths, RunInputs
from benchmark.client import BenchmarkClient
from benchmark.drivers.base import CapabilityContext, CapabilityDriver, CapabilityResult
from benchmark.ingest import ChapterIngest, IngestResult
from benchmark.ingest_events import IngestEvent
from benchmark.provision import ProvisionOutcome

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from benchmark.config_schemas import BenchmarkConfig
    from benchmark.runner import ProvisionFn
    from benchmark.runner_failure import RunFailure

STARTED_AT: Final[datetime] = datetime(2026, 8, 31, 10, 0, 0, tzinfo=UTC)
FINISHED_AT: Final[datetime] = datetime(2026, 8, 31, 10, 3, 0, tzinfo=UTC)
BASE_URL: Final[str] = "http://127.0.0.1:18080"
NOVEL_ID: Final[str] = "novel-1"
WIZARD_NOVEL_ID: Final[str] = "wizard-novel"
GIT_SHA: Final[str] = "fixed-commit-sha"
COMPOSE_SHA256: Final[str] = "c" * 64

FILTER: Final[tuple[str, ...]] = (
    "CAP-IN-01",
    "CAP-OUT-01",
    "CAP-OUT-03",
    "CAP-OUT-07",
    "CAP-CHK-05",
)


# ---------------------------------------------------------------------------
# Sequence log + stack fake
# ---------------------------------------------------------------------------


class RunLog:
    """Ordered stage/event log — the wiring test's sequence assertion."""

    def __init__(self) -> None:
        self.entries: list[str] = []

    def push(self, entry: str) -> None:
        self.entries.append(entry)


class FakeStack:
    """``RunStack`` seam: records up/teardown/facts, serves canned facts."""

    def __init__(self, log: RunLog) -> None:
        self._log = log
        self.teardown_calls = 0

    def up(self) -> str:
        self._log.push("stack.up")
        return BASE_URL

    def teardown(self, *, verify: bool = True) -> None:
        self.teardown_calls += 1
        self._log.push(f"stack.teardown(verify={verify})")

    def facts(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        self._log.push("stack.facts")
        return COMPOSE_SHA256, (("api", f"sha256:{'d' * 64}"),)


class FakeClock:
    """Time seam: STARTED_AT first, then FINISHED_AT (repeated)."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return STARTED_AT if self.calls == 1 else FINISHED_AT


# ---------------------------------------------------------------------------
# Client (real BenchmarkClient over a scripted transport) + provision fake
# ---------------------------------------------------------------------------


def make_client_factory(log: RunLog) -> Callable[[str, float], BenchmarkClient]:
    """Client seam: a REAL client whose transport answers /openapi.json only."""

    def factory(base_url: str, timeout_seconds: float) -> BenchmarkClient:
        log.push("client")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/openapi.json":
                return httpx.Response(200, json={"info": {"title": "narrare", "version": "0.1.0"}})
            return httpx.Response(500, json={"detail": f"unscripted {request.url.path}"})

        return BenchmarkClient(base_url, timeout_seconds, transport=httpx.MockTransport(handler))

    return factory


def fake_provision(log: RunLog) -> ProvisionFn:
    """Provision seam: records the stage, returns a fresh-wizard outcome."""

    def provision(client: BenchmarkClient, config: BenchmarkConfig) -> ProvisionOutcome:
        log.push("provision")
        return ProvisionOutcome(already_configured=False, novel_id=WIZARD_NOVEL_ID)

    return provision


# ---------------------------------------------------------------------------
# Ingest fake (T8 rider: entry ids ride on the result)
# ---------------------------------------------------------------------------


def make_ingest_result() -> IngestResult:
    """Two ingested chapters; apply responses created entry-1/entry-2."""
    chapters = (
        ChapterIngest(
            stem="ch-01",
            chapter_id="chapter-1",
            candidates=3,
            endorsed=3,
            created_entries=1,
            updated_entries=0,
            created_entry_ids=("entry-1",),
            updated_entry_ids=(),
        ),
        ChapterIngest(
            stem="ch-02",
            chapter_id="chapter-2",
            candidates=2,
            endorsed=2,
            created_entries=1,
            updated_entries=1,
            created_entry_ids=("entry-2",),
            updated_entry_ids=("entry-1",),
        ),
    )
    return IngestResult(novel_id=NOVEL_ID, chapters=chapters)


def fake_ingest(log: RunLog, *, error: Exception | None = None) -> Callable[..., IngestResult]:
    """Ingest seam: records the stage, appends one sink event, fails on demand."""

    def ingest(
        _client: BenchmarkClient,
        _chapters: Sequence[object],
        *,
        variant: str,
        mode: str,
        events: list[IngestEvent],
        sleeper: Callable[[float], None],
    ) -> IngestResult:
        log.push("ingest")
        assert variant and mode and sleeper is not None
        if error is not None:
            raise error
        events.append(
            IngestEvent(
                step="create_novel",
                chapter_stem=None,
                method="POST",
                path="/api/v1/novels",
                status=201,
                elapsed_seconds=0.1,
                request_body=None,
                response_body={"id": NOVEL_ID},
            )
        )
        return make_ingest_result()

    return ingest


# ---------------------------------------------------------------------------
# Driver fakes (scripted CapabilityResults; ctx + targets recorded)
# ---------------------------------------------------------------------------


class ScriptedDriver:
    """One capability's driver: records the drive + the ctx it received."""

    def __init__(
        self,
        cap_id: str,
        log: RunLog,
        results: dict[str, CapabilityResult],
        contexts: list[tuple[str, CapabilityContext]],
    ) -> None:
        self._cap_id = cap_id
        self._log = log
        self._results = results
        self._contexts = contexts

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        self._log.push(f"drive:{self._cap_id}")
        self._contexts.append((self._cap_id, ctx))
        scripted = self._results.get(self._cap_id)
        if scripted is not None:
            return scripted
        return CapabilityResult.ok(self._cap_id, parsed=None, elapsed_seconds=0.5)


class FakeDrivers:
    """Driver-provider seam with per-cap scripted results + ctx capture."""

    def __init__(self, log: RunLog, results: dict[str, CapabilityResult] | None = None) -> None:
        self.log = log
        self.results = dict(results or {})
        self.contexts: list[tuple[str, CapabilityContext]] = []

    def driver_for(self, cap_id: str) -> CapabilityDriver:
        return ScriptedDriver(cap_id, self.log, self.results, self.contexts)

    def targets_of(self, cap_id: str) -> dict[str, str]:
        for context_cap_id, ctx in self.contexts:
            if context_cap_id == cap_id:
                return dict(ctx.targets)
        raise AssertionError(f"capability {cap_id} was never driven")


# ---------------------------------------------------------------------------
# Artifact writers (recording) + git fake
# ---------------------------------------------------------------------------


class RecordingArtifacts:
    """Artifact-writer seam: records (out_dir, inputs, git sha) calls."""

    def __init__(self, log: RunLog) -> None:
        self.log = log
        self.calls: list[tuple[Path, RunInputs, str]] = []

    def write(
        self, out_dir: Path, inputs: RunInputs, *, git_commit: Callable[[], str]
    ) -> ArtifactPaths:
        self.log.push("artifacts")
        self.calls.append((out_dir, inputs, git_commit()))
        run_dir = out_dir / "wired-run"
        return ArtifactPaths(
            run_id="wired-run",
            run_dir=run_dir,
            results=run_dir,
            answers=run_dir,
            events=run_dir,
            manifest=run_dir,
            overview=run_dir,
        )


class RecordingFailures:
    """Failure-writer seam: records (out_dir, failure, events snapshot)."""

    def __init__(self, log: RunLog) -> None:
        self.log = log
        self.calls: list[tuple[Path, RunFailure, tuple[IngestEvent, ...]]] = []

    def write(self, out_dir: Path, failure: RunFailure, events: Sequence[IngestEvent]) -> Path:
        self.log.push("failure_artifacts")
        self.calls.append((out_dir, failure, tuple(events)))
        return out_dir / "failure-dir"


def fake_git_commit(log: RunLog) -> Callable[[], str]:
    def git_commit() -> str:
        log.push("git")
        return GIT_SHA

    return git_commit
