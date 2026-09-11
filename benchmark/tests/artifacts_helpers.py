"""Fixture builders for the run-artifacts writer tests (Task 14).

Plain helpers, no fixtures, no network (``scoring_helpers`` precedent).
One synthetic-but-consistent scoring triple: build quality and retrieval
are produced by the REAL Task-11/13 scorers over a small synthetic
reference/KB (aggregates stay mathematically consistent), detection is a
direct ``DetectionReport`` (a plain frozen record — the Task-12 scorer
would need the full registry; the writer only serializes it).
Secret-bearing config values (``SECRET_API_KEY``/``SECRET_PASSWORD``)
exist ONLY to prove the redaction sweep; they are never real secrets.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from benchmark.artifacts_records import CapabilityAnswer, RunInputs, StackFacts
from benchmark.config_schemas import (
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    LlmConfig,
    RunConfig,
    StackConfig,
)
from benchmark.drivers.base import CapabilityStatus
from benchmark.drivers.in_records import ExtractionRecord
from benchmark.drivers.out_records import SearchRecord
from benchmark.ingest_events import IngestEvent
from benchmark.scoring.build_quality import score_build_quality
from benchmark.scoring.detection_records import (
    DetectionReport,
    DetectionScore,
    FalsePositive,
    MatchedError,
    MissedError,
)
from benchmark.scoring.retrieval import score_retrieval
from benchmark.tests.scoring_helpers import (
    detail,
    edge,
    make_reference,
    ref_entity,
    ref_fact,
    ref_relation,
    summary,
)

if TYPE_CHECKING:
    from benchmark.scoring.retrieval_records import RetrievalScore
    from benchmark.scoring.score_records import BuildQualityScore

SECRET_API_KEY = "sk-SUPERSECRET-KEY-VALUE"
SECRET_PASSWORD = "hunter2-PASSWORD-VALUE"

STARTED_AT = datetime(2026, 8, 31, 10, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 8, 31, 10, 5, 0, tzinfo=UTC)
GIT_COMMIT = "fixed-commit-sha"


# ---------------------------------------------------------------------------
# Config + stack facts
# ---------------------------------------------------------------------------


def make_config() -> BenchmarkConfig:
    """Full config with secret-bearing auth/llm fields (for the sweep)."""
    return BenchmarkConfig(
        stack=StackConfig(project_name="bench-run", port_range_low=30000, port_range_high=30010),
        api=ApiConfig(base_url=None, timeout_seconds=30.0),
        auth=AuthConfig(email="bench@example.com", password=SECRET_PASSWORD),
        llm=LlmConfig(
            provider="zai",
            api_key=SECRET_API_KEY,
            model="glm-5.3-flash",
            ollama_url="http://127.0.0.1:11434",
            zai_endpoint="https://api.z.ai/api/coding/paas/v4",
        ),
        run=RunConfig(
            variants=["clean", "light", "complex"],
            modes=["incremental", "import"],
            keep_stack=False,
            capabilities=[],
        ),
    )


def make_stack() -> StackFacts:
    return StackFacts(
        compose_sha256="c" * 64,
        image_digests=(("api", f"sha256:{'d' * 64}"),),
        api_version={"version": "0.1.0", "commit": "deadbeef"},
    )


# ---------------------------------------------------------------------------
# Scoring triple (build quality + retrieval via the real scorers)
# ---------------------------------------------------------------------------


def make_reference_and_kb() -> tuple[BuildQualityScore, RetrievalScore]:
    """Score build quality over a 3-entity synthetic KB (1 fact missing)."""
    reference = make_reference(
        persons=(
            ref_entity("p1", "Anna Meyer", facts=(ref_fact("F001", "age_stated", "24"),)),
            ref_entity("p2", "Berta Kalt", facts=(ref_fact("F002", "age_stated", "31"),)),
            ref_entity("p3", "Ben Schulz"),
        ),
        relations=(ref_relation("R001", "p1", "sibling_of", "p3"),),
    )
    entries = (
        summary("e1", "Anna Meyer"),
        summary("e2", "Berta Kalt"),
        summary("e3", "Ben Schulz"),
    )
    details = (
        detail("e1", name="Anna Meyer", metadata={"age_stated": 24}),
        detail("e2", name="Berta Kalt"),
        detail(
            "e3",
            name="Ben Schulz",
            relationships=(
                edge(
                    "rel-1",
                    "sibling_of",
                    "e1",
                    "e3",
                    source_name="Anna Meyer",
                    target_name="Ben Schulz",
                ),
            ),
        ),
    )
    return score_build_quality(reference, entries, details), score_retrieval(reference, details)


def make_detection() -> DetectionReport:
    """One matrix cell + one row per evidence kind (id traceability)."""
    return DetectionReport(
        matrix=(
            DetectionScore(
                capability="CAP-CHK-01",
                error_class="L",
                expected=2,
                tp=1,
                fp=1,
                fn=1,
                precision=0.5,
                recall=0.5,
                f1=0.5,
            ),
        ),
        true_positives=(MatchedError("L01", "L", "CAP-CHK-01", "issues[0]"),),
        false_negatives=(MissedError("L03", "L"),),
        false_positives=(FalsePositive("CAP-CHK-01", "issues[1]", "hafen liegt im sueden"),),
    )


# ---------------------------------------------------------------------------
# Answers + raw events
# ---------------------------------------------------------------------------


def make_answers() -> tuple[CapabilityAnswer, ...]:
    """One answer per status; parsed records are real driver records."""
    return (
        CapabilityAnswer(
            cap_id="CAP-IN-01",
            status=CapabilityStatus.OK,
            elapsed_seconds=1.25,
            parsed=ExtractionRecord(
                chapter_id="ch-01",
                candidates=(),
                analysis_notes="re-extraction clean",
                created=("e1",),
                updated=(),
            ),
        ),
        CapabilityAnswer(
            cap_id="CAP-OUT-01",
            status=CapabilityStatus.OK,
            elapsed_seconds=0.5,
            parsed=SearchRecord(
                query="Anna", entries=(summary("e1", "Anna Meyer"),), total=1, pages_fetched=1
            ),
        ),
        CapabilityAnswer(
            cap_id="CAP-CHK-02",
            status=CapabilityStatus.SKIPPED,
            elapsed_seconds=0.0,
            reason="series canon skipped: corpus provides no series (structural gating)",
        ),
        CapabilityAnswer(
            cap_id="CAP-CHK-05",
            status=CapabilityStatus.ERROR,
            elapsed_seconds=30.0,
            reason="sse stream deadline exceeded",
        ),
    )


def make_events() -> tuple[IngestEvent, ...]:
    """Pre-sanitized events (production sanitizes at ``record`` time)."""
    return (
        IngestEvent(
            step="create_novel",
            chapter_stem=None,
            method="POST",
            path="/api/v1/novels",
            status=201,
            elapsed_seconds=0.2,
            request_body={"title": "Testnovelle"},
            response_body={"id": "novel-1", "title": "Testnovelle"},
        ),
        IngestEvent(
            step="provision_llm",
            chapter_stem=None,
            method="POST",
            path="/api/v1/setup/steps/4",
            status=200,
            elapsed_seconds=0.3,
            request_body={"provider": "zai", "api_key": "[REDACTED]", "model": "glm-5.3-flash"},
            response_body={"status": "ok"},
        ),
    )


# ---------------------------------------------------------------------------
# Aggregate inputs
# ---------------------------------------------------------------------------


def make_inputs() -> RunInputs:
    build_quality, retrieval = make_reference_and_kb()
    return RunInputs(
        variant="light",
        mode="incremental",
        corpus_version=1,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
        config=make_config(),
        build_quality=build_quality,
        detection=make_detection(),
        retrieval=retrieval,
        answers=make_answers(),
        events=make_events(),
        stack=make_stack(),
        fp_baseline=False,
    )


class FakeGitCommit:
    """Injectable git-commit provider pinning a fixed sha."""

    def __init__(self, commit: str = GIT_COMMIT) -> None:
        self._commit = commit
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self._commit
