"""Runner wiring tests (plan Task 15) — orchestration with ALL collaborators faked.

Pinned: the stage SEQUENCE (stack → client → provision → ingest →
drive x N → scoring KB-state fetch → facts → artifacts → teardown),
teardown ALWAYS (success, failure, keep-stack), partial-failure
artifacts + re-raise, capability filtering (incl. unknown and duplicate
ids failing BEFORE the stack is created), T8-rider target population,
chapter_map resolution in real detection scoring, clean-variant empty
detection, the structural series skip via a REAL series driver, scoring
that consumes only OK parsed records, and the scoring-phase KB-state
fetch that decouples build quality from capability selection. Individual
seam units live in ``test_runner_units.py``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from benchmark.artifacts_records import RunInputs
from benchmark.capabilities import UnknownCapabilityError
from benchmark.capabilities_registry import CAPABILITIES
from benchmark.drivers.base import CapabilityResult, CapabilityStatus
from benchmark.drivers.check_direction_series import SeriesConsistencyDriver
from benchmark.ingest import IngestError
from benchmark.ingest_events import IngestEvent
from benchmark.runner import run
from benchmark.scoring.resolution_match import ResolutionScore
from benchmark.tests.runner_fixtures import Wiring, voice_check_record
from benchmark.tests.runner_helpers import (
    COMPOSE_SHA256,
    FILTER,
    FINISHED_AT,
    GIT_SHA,
    STARTED_AT,
)

if TYPE_CHECKING:
    from pathlib import Path

    from benchmark.client import BenchmarkClient
    from benchmark.corpus_views import Chapter


# ---------------------------------------------------------------------------
# Wiring: happy path
# ---------------------------------------------------------------------------


def test_run_wires_all_stages_in_order(tmp_path: Path) -> None:
    wired = Wiring(tmp_path)

    paths = run(wired.request, wired.deps)

    assert paths.run_id == "wired-run"
    assert wired.log.entries == [
        "stack.up",
        "client",
        "provision",
        "ingest",
        *(f"drive:{cap_id}" for cap_id in FILTER),
        "score_fetch",
        "stack.facts",
        "artifacts",  # the writer call; the git provider fires inside it
        "git",
        "stack.teardown(verify=True)",
    ]


def test_run_without_filter_drives_every_registry_entry_in_order(tmp_path: Path) -> None:
    wired = Wiring(tmp_path, capabilities=())

    run(wired.request, wired.deps)

    drives = [entry for entry in wired.log.entries if entry.startswith("drive:")]
    assert drives == [f"drive:{spec.cap_id}" for spec in CAPABILITIES]


def test_run_hands_ingest_populated_targets_to_drivers(tmp_path: Path) -> None:
    wired = Wiring(tmp_path)

    run(wired.request, wired.deps)

    for cap_id in FILTER:
        assert wired.drivers.targets_of(cap_id) == {
            "chapter_id": "chapter-1",
            "entry_id": "entry-1",
        }
    ctx = wired.drivers.contexts[0][1]
    assert ctx.novel_id == "novel-1"
    assert dict(ctx.chapter_ids) == {"ch-01": "chapter-1", "ch-02": "chapter-2"}


def test_run_writes_artifacts_with_scored_run_inputs(tmp_path: Path) -> None:
    wired = Wiring(tmp_path)

    run(wired.request, wired.deps)

    assert len(wired.artifacts.calls) == 1
    out_dir, inputs, git_sha = wired.artifacts.calls[0]
    assert out_dir == tmp_path / "out"
    assert git_sha == GIT_SHA
    assert isinstance(inputs, RunInputs)
    assert inputs.variant == "light" and inputs.mode == "incremental"
    assert inputs.started_at == STARTED_AT and inputs.finished_at == FINISHED_AT
    assert inputs.corpus_version == 1
    assert inputs.config is wired.request.config
    assert inputs.fp_baseline is False
    assert inputs.stack.compose_sha256 == COMPOSE_SHA256
    assert inputs.stack.api_version == {
        "source": "GET /openapi.json info.version",
        "version": "0.1.0",
    }
    assert [answer.cap_id for answer in inputs.answers] == list(FILTER)
    assert all(answer.status is CapabilityStatus.OK for answer in inputs.answers)
    assert inputs.events[0].step == "create_novel"
    # real scoring over the SCORING FETCH's KB state: entity found, fact found
    assert inputs.build_quality.entity_coverage == 1.0
    assert inputs.build_quality.fact_coverage == 1.0
    # real detection: the chapter-pinned flagged line resolved via chapter_map
    assert [tp.error_id for tp in inputs.detection.true_positives] == ["L01"]
    assert inputs.detection.false_negatives == ()


def test_scoring_fetch_receives_the_runs_identity(tmp_path: Path) -> None:
    wired = Wiring(tmp_path)

    run(wired.request, wired.deps)

    assert wired.score_fetch.calls == [
        {
            "novel_id": "novel-1",
            "chapter_ids": {"ch-01": "chapter-1", "ch-02": "chapter-2"},
            "targets": {"chapter_id": "chapter-1", "entry_id": "entry-1"},
            "event_count": 1,
        }
    ]


def test_build_quality_scores_even_without_out_capabilities_driven(tmp_path: Path) -> None:
    """The bug this fixes: ``--capabilities`` without CAP-OUT-01/03 used to
    leave build quality with NO evidence (every entity 'missing'). Scoring
    now fetches the full KB state itself — independent of the selection."""
    wired = Wiring(tmp_path, capabilities=("CAP-IN-01",))

    run(wired.request, wired.deps)

    _, inputs, _ = wired.artifacts.calls[0]
    assert [answer.cap_id for answer in inputs.answers] == ["CAP-IN-01"]
    assert inputs.build_quality.entity_coverage == 1.0
    assert inputs.build_quality.fact_coverage == 1.0


def resolution_result() -> CapabilityResult:
    """An OK CAP-IN-10 answer (empty record — the fixture KB has no duplicates)."""
    from benchmark.drivers.in_records import BandStats, ResolutionRecord

    record = ResolutionRecord(
        suggestions=(),
        stats=BandStats(review=0, auto_eligible=0, suppressed=0),
        cache_hit=False,
        merges=(),
    )
    return CapabilityResult.ok("CAP-IN-10", parsed=record, elapsed_seconds=1.0)


def test_run_carries_the_resolution_score_into_run_inputs(tmp_path: Path) -> None:
    """ADR-085 P6 wiring pin: the scorer's resolution output MUST reach
    ``RunInputs`` — dropping that link (fix round 1) silently voids the
    results.json resolution section while every other gate stays green."""
    wired = Wiring(
        tmp_path, results={"CAP-IN-10": resolution_result()}, capabilities=("CAP-IN-10",)
    )

    run(wired.request, wired.deps)

    _, inputs, _ = wired.artifacts.calls[0]
    assert inputs.resolution == ResolutionScore(
        precision=1.0,
        recall=1.0,
        auto_band_ok=True,
        distractor_never_suggested=True,
        expected_pair_count=0,  # fixture KB: one entry, no duplicate pair
        suggested_count=0,
        endorsed_count=0,
        endorsed_expected_pairs=0,
    )


def test_run_without_cap_in_10_leaves_run_inputs_resolution_absent(tmp_path: Path) -> None:
    wired = Wiring(tmp_path, capabilities=("CAP-IN-01",))

    run(wired.request, wired.deps)

    _, inputs, _ = wired.artifacts.calls[0]
    assert inputs.resolution is None


def test_teardown_verifies_after_success(tmp_path: Path) -> None:
    wired = Wiring(tmp_path)

    run(wired.request, wired.deps)

    log = wired.log.entries
    assert log[-1] == "stack.teardown(verify=True)"
    assert log.index("artifacts") < log.index("stack.teardown(verify=True)")


def test_keep_stack_skips_teardown(tmp_path: Path) -> None:
    wired = Wiring(tmp_path, keep_stack=True)

    run(wired.request, wired.deps)

    assert not any(entry.startswith("stack.teardown") for entry in wired.log.entries)


# ---------------------------------------------------------------------------
# Wiring: capability filter + structural skip
# ---------------------------------------------------------------------------


def test_capability_filter_drives_only_selected(tmp_path: Path) -> None:
    wired = Wiring(tmp_path, capabilities=("CAP-OUT-01", "CAP-CHK-05"))

    run(wired.request, wired.deps)

    assert [entry for entry in wired.log.entries if entry.startswith("drive:")] == [
        "drive:CAP-OUT-01",
        "drive:CAP-CHK-05",
    ]
    _, inputs, _ = wired.artifacts.calls[0]
    assert [answer.cap_id for answer in inputs.answers] == ["CAP-OUT-01", "CAP-CHK-05"]


def test_unknown_capability_fails_before_the_stack_is_created(tmp_path: Path) -> None:
    wired = Wiring(tmp_path, capabilities=("CAP-NOPE-99",))

    with pytest.raises(UnknownCapabilityError, match="CAP-NOPE-99"):
        run(wired.request, wired.deps)

    assert wired.log.entries == []


def test_duplicate_capability_ids_fail_before_the_stack_is_created(tmp_path: Path) -> None:
    wired = Wiring(tmp_path, capabilities=("CAP-OUT-01", "CAP-OUT-01"))

    with pytest.raises(ValueError, match="duplicate"):
        run(wired.request, wired.deps)

    assert wired.log.entries == []


def test_series_scoped_capability_skips_structurally_via_targets(tmp_path: Path) -> None:
    """REAL series driver (fakes don't gate): without ``series_id`` in the
    run targets, ``require_target`` skips it structurally — no fabricated id."""
    wired = Wiring(tmp_path, capabilities=("CAP-CHK-02",))
    wired.deps = replace(wired.deps, driver_for_fn=lambda _cap_id: SeriesConsistencyDriver())

    run(wired.request, wired.deps)

    _, inputs, _ = wired.artifacts.calls[0]
    answer = inputs.answers[0]
    assert answer.status is CapabilityStatus.SKIPPED
    assert answer.parsed is None
    assert answer.reason is not None and answer.reason.startswith("structural:")


def test_clean_variant_scores_an_empty_detection_report(tmp_path: Path) -> None:
    wired = Wiring(tmp_path, variant="clean")

    run(wired.request, wired.deps)

    _, inputs, _ = wired.artifacts.calls[0]
    assert inputs.detection.matrix == ()
    assert inputs.detection.true_positives == ()
    assert inputs.detection.false_negatives == ()
    assert inputs.detection.false_positives == ()


def test_scoring_consumes_only_ok_parsed_records(tmp_path: Path) -> None:
    errored = CapabilityResult.error("CAP-CHK-05", reason="sse deadline exceeded")
    wired = Wiring(tmp_path, results={"CAP-CHK-05": errored})

    run(wired.request, wired.deps)

    _, inputs, _ = wired.artifacts.calls[0]
    assert inputs.detection.matrix == ()  # no OK check report → no matrix rows
    assert [row.error_id for row in inputs.detection.false_negatives] == ["L01"]
    assert inputs.build_quality.entity_coverage == 1.0  # scoring fetch runs regardless


def test_wrong_chapter_pin_yields_false_negative_not_false_match(tmp_path: Path) -> None:
    """chapter_map resolution is fail-closed: an unresolvable chapter pin
    never matches — the error is a plain FN, never a false TP."""
    pinned = CapabilityResult.ok(
        "CAP-CHK-05", parsed=voice_check_record("chapter-9"), elapsed_seconds=1.0
    )
    wired = Wiring(tmp_path, results={"CAP-CHK-05": pinned}, capabilities=("CAP-CHK-05",))

    run(wired.request, wired.deps)

    _, inputs, _ = wired.artifacts.calls[0]
    assert inputs.detection.true_positives == ()
    assert [row.error_id for row in inputs.detection.false_negatives] == ["L01"]


# ---------------------------------------------------------------------------
# Wiring: partial failure
# ---------------------------------------------------------------------------


def test_ingest_failure_writes_failure_artifacts_then_teardown_then_raises(
    tmp_path: Path,
) -> None:
    failure = IngestError(step="extract", chapter_id="chapter-1", summary="HTTP 500: down")
    wired = Wiring(tmp_path, ingest_error=failure)

    with pytest.raises(IngestError):
        run(wired.request, wired.deps)

    assert wired.log.entries == [
        "stack.up",
        "client",
        "provision",
        "ingest",
        "failure_artifacts",
        "stack.teardown(verify=True)",
    ]
    assert len(wired.failures.calls) == 1
    out_dir, recorded, events = wired.failures.calls[0]
    assert out_dir == tmp_path / "out"
    assert recorded.stage == "ingest"
    assert recorded.error_type == "IngestError"
    assert recorded.error_message == str(failure)  # payload-free by construction
    assert recorded.keep_stack is False
    assert recorded.event_count == 0  # failure raised BEFORE any event was recorded
    assert events == ()
    assert wired.artifacts.calls == []  # no full-run artifacts on failure


def test_ingest_failure_after_events_keeps_the_sink_snapshot(tmp_path: Path) -> None:
    """The failure writer receives the sanitized event sink SO FAR."""
    failure = IngestError(step="extract", chapter_id="chapter-1", summary="HTTP 500: down")
    wired = Wiring(tmp_path, ingest_error=failure)

    def ingest_then_fail(
        _client: BenchmarkClient,
        _chapters: tuple[Chapter, ...],
        *,
        variant: str,
        mode: str,
        events: list[IngestEvent],
        sleeper: object,
    ) -> object:
        wired.log.push("ingest")
        assert variant and mode and sleeper is not None
        events.append(
            IngestEvent(
                step="create_chapter",
                chapter_stem="ch-01",
                method="POST",
                path="/api/v1/novels/novel-1/chapters",
                status=201,
                elapsed_seconds=0.05,
                request_body=None,
                response_body={"id": "chapter-1"},
            )
        )
        raise failure

    wired.deps = replace(wired.deps, ingest_fn=ingest_then_fail)

    with pytest.raises(IngestError):
        run(wired.request, wired.deps)

    _out_dir, recorded, events = wired.failures.calls[0]
    assert recorded.event_count == 1
    assert len(events) == 1
