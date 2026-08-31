"""Run-artifacts writer tests (Task 14).

TDD RED state: this module was written BEFORE its implementation existed
(``benchmark/artifacts*.py``); first collection fails with
``ModuleNotFoundError`` (documented in the task report). Coverage:
artifact shape for all four files + the raw-event sink, the run-id
counter, manifest fingerprint (redacted-dict hash, never raw values),
determinism (same inputs → byte-identical trees), loud validation,
atomicity (serialization failure leaves NO new files), and the
secret-redaction sweep over the full artifact tree.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

import pytest

from benchmark.artifacts import write_run_artifacts
from benchmark.artifacts_records import ArtifactError, ArtifactPaths, CapabilityAnswer, RunInputs
from benchmark.capabilities import UNAVAILABLE_SURFACES
from benchmark.drivers.base import CapabilityStatus
from benchmark.tests.artifacts_helpers import (
    FINISHED_AT,
    GIT_COMMIT,
    SECRET_API_KEY,
    SECRET_PASSWORD,
    STARTED_AT,
    FakeGitCommit,
    make_config,
    make_inputs,
)

if TYPE_CHECKING:
    from pathlib import Path

RUN_ID_1 = "2026-08-31-light-incremental-1"


def write(tmp_path: Path, inputs: RunInputs | None = None) -> ArtifactPaths:
    return write_run_artifacts(
        tmp_path, make_inputs() if inputs is None else inputs, git_commit=FakeGitCommit()
    )


def read_json(path: Path) -> dict[str, Any]:
    """Parse a JSON object file (``Any`` per the ``test_guard`` test precedent)."""
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    return cast("dict[str, Any]", loaded)


# ---------------------------------------------------------------------------
# Run id + directory layout
# ---------------------------------------------------------------------------


def test_run_id_format_and_counter_increments_per_day_variant_mode(tmp_path: Path) -> None:
    first = write(tmp_path)
    assert first.run_id == RUN_ID_1
    assert first.run_dir == tmp_path / RUN_ID_1
    second = write(tmp_path)
    assert second.run_id == "2026-08-31-light-incremental-2"
    for paths in (first, second):
        assert sorted(p.name for p in paths.run_dir.iterdir()) == [
            "answers.jsonl",
            "events.jsonl",
            "manifest.json",
            "overview.md",
            "results.json",
        ]


def test_next_run_id_counts_within_day_and_variant_mode_only(tmp_path: Path) -> None:
    write(tmp_path)
    (tmp_path / "2026-08-30-light-incremental-9").mkdir()
    (tmp_path / "2026-08-31-complex-incremental-5").mkdir()
    (tmp_path / "unrelated").mkdir()
    third = write(tmp_path)
    assert third.run_id == "2026-08-31-light-incremental-2"


# ---------------------------------------------------------------------------
# results.json shape
# ---------------------------------------------------------------------------


def test_results_json_has_scored_surfaces_with_traceable_ids(tmp_path: Path) -> None:
    results = read_json(write(tmp_path).results)
    assert sorted(results) == ["build_quality", "detection", "retrieval"]
    build = results["build_quality"]
    assert build["entity_coverage"] == 1.0
    assert build["fact_coverage"] == 0.5
    assert build["fact_precision"] == 1.0
    assert build["relation_coverage"] == 1.0
    assert [row["ref_id"] for row in build["facts"]] == ["F001", "F002"]
    assert [row["status"] for row in build["facts"]] == ["found", "missing"]
    assert build["relations"][0]["ref_id"] == "R001"
    matrix = results["detection"]["matrix"]
    assert matrix == [
        {
            "capability": "CAP-CHK-01",
            "error_class": "L",
            "expected": 2,
            "tp": 1,
            "fp": 1,
            "fn": 1,
            "precision": 0.5,
            "recall": 0.5,
            "f1": 0.5,
        }
    ]
    assert results["detection"]["true_positives"][0]["error_id"] == "L01"
    assert results["detection"]["false_negatives"][0]["error_id"] == "L03"
    assert results["detection"]["false_positives"][0]["fingerprint"] == "hafen liegt im sueden"
    retrieval = results["retrieval"]
    assert sorted(retrieval) == ["answer_coverage", "answer_precision", "coverage", "outcomes"]
    assert retrieval["answer_coverage"] == pytest.approx(2 / 3)
    assert [row["ref_id"] for row in retrieval["outcomes"]] == ["F001", "F002", "R001"]
    coverage = {row["capability"]: row for row in retrieval["coverage"]}
    assert len(coverage) == 10
    assert coverage["CAP-OUT-03"]["surface"] == "scored"
    assert coverage["CAP-OUT-03"]["driven"] is True
    assert coverage["CAP-OUT-05"]["surface"] == "skipped"


def test_results_json_contains_no_timestamps(tmp_path: Path) -> None:
    content = write(tmp_path).results.read_text(encoding="utf-8")
    assert STARTED_AT.isoformat() not in content
    assert FINISHED_AT.isoformat() not in content


# ---------------------------------------------------------------------------
# answers.jsonl shape
# ---------------------------------------------------------------------------


def test_answers_jsonl_rows_are_sorted_and_projected(tmp_path: Path) -> None:
    lines = write(tmp_path).answers.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert [row["cap_id"] for row in rows] == [
        "CAP-CHK-02",
        "CAP-CHK-05",
        "CAP-IN-01",
        "CAP-OUT-01",
    ]
    skipped, errored, extraction, search = rows
    assert skipped["status"] == "skipped"
    assert skipped["reason"].startswith("series canon skipped")
    assert skipped["parsed"] is None
    assert errored["status"] == "error"
    assert errored["reason"] == "sse stream deadline exceeded"
    assert extraction["status"] == "ok"
    assert extraction["parsed"] == {
        "chapter_id": "ch-01",
        "candidates": [],
        "analysis_notes": "re-extraction clean",
        "created": ["e1"],
        "updated": [],
    }
    assert search["parsed"]["query"] == "Anna"
    assert search["parsed"]["total"] == 1
    assert {row["elapsed_seconds"] for row in rows} == {0.0, 0.5, 1.25, 30.0}


# ---------------------------------------------------------------------------
# manifest.json shape + fingerprint
# ---------------------------------------------------------------------------


def test_manifest_is_complete_and_fingerprints_the_redacted_config(tmp_path: Path) -> None:
    manifest = read_json(write(tmp_path).manifest)
    assert manifest["run_id"] == RUN_ID_1
    assert manifest["started_at"] == STARTED_AT.isoformat()
    assert manifest["finished_at"] == FINISHED_AT.isoformat()
    assert manifest["git_commit"] == GIT_COMMIT
    assert manifest["corpus_version"] == 1
    assert manifest["variant"] == "light"
    assert manifest["mode"] == "incremental"
    canonical = json.dumps(make_config().redacted_dict(), sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert manifest["config_fingerprint"] == {
        "provider": "zai",
        "model": "glm-5.3-flash",
        "config_hash": f"sha256:{expected_hash}",
    }
    assert manifest["stack"] == {
        "compose_sha256": "c" * 64,
        "image_digests": {"api": f"sha256:{'d' * 64}"},
        "api_version": {"version": "0.1.0", "commit": "deadbeef"},
    }
    assert manifest["capabilities"] == {"driven": 2, "errored": 1, "skipped": 1}


# ---------------------------------------------------------------------------
# events.jsonl (raw-event sink)
# ---------------------------------------------------------------------------


def test_sink_writes_sanitized_events_verbatim_as_jsonl(tmp_path: Path) -> None:
    lines = write(tmp_path).events.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["step"] == "create_novel"
    assert first["request_body"] == {"title": "Testnovelle"}
    second = json.loads(lines[1])
    assert second["request_body"]["api_key"] == "[REDACTED]"
    assert SECRET_API_KEY not in lines[1]


# ---------------------------------------------------------------------------
# overview.md
# ---------------------------------------------------------------------------


def test_overview_renders_run_header_and_all_tables(tmp_path: Path) -> None:
    overview = write(tmp_path).overview.read_text(encoding="utf-8")
    assert f"# KB Benchmark Run {RUN_ID_1}" in overview
    assert "| Variant | light |" in overview
    assert "| Mode | incremental |" in overview
    assert f"| Git commit | {GIT_COMMIT} |" in overview
    assert "glm-5.3-flash" in overview and "zai" in overview
    assert "| Corpus version | 1 |" in overview
    assert "2 driven" in overview and "1 errored" in overview and "1 skipped" in overview
    assert "| Entity coverage | 1.000 |" in overview
    assert "| Fact coverage | 0.500 |" in overview
    assert "| Fact precision | 1.000 |" in overview
    assert "| Relation coverage | 1.000 |" in overview
    assert "| Answer coverage | 0.667 |" in overview
    assert "| Answer precision | 1.000 |" in overview


def test_overview_detection_matrix_and_fp_baseline_note_per_capability(tmp_path: Path) -> None:
    overview = write(tmp_path).overview.read_text(encoding="utf-8")
    assert "| CAP-CHK-01 | L | 2 | 1 | 1 | 1 | 0.500 | 0.500 | 0.500 |" in overview
    assert "CAP-CHK-01 | 1 |" in overview  # FP-baseline row with the capability's fp
    assert "fingerprint" in overview and "clean run" in overview


def test_overview_retrieval_and_skipped_tables_with_reasons(tmp_path: Path) -> None:
    overview = write(tmp_path).overview.read_text(encoding="utf-8")
    assert "| CAP-OUT-03 | scored | yes |" in overview
    assert "| CAP-OUT-05 | skipped | no |" in overview
    assert "series canon skipped" in overview
    for unavailable in UNAVAILABLE_SURFACES:
        assert unavailable.label in overview
        assert unavailable.reason in overview
    assert "sse stream deadline exceeded" in overview


# ---------------------------------------------------------------------------
# Determinism + secrets + atomicity + validation
# ---------------------------------------------------------------------------


def test_same_inputs_produce_byte_identical_artifacts(tmp_path: Path) -> None:
    root_a, root_b = tmp_path / "a", tmp_path / "b"
    first = write(root_a)
    second = write(root_b)
    for name in ("results.json", "overview.md", "manifest.json", "answers.jsonl", "events.jsonl"):
        assert (first.run_dir / name).read_bytes() == (second.run_dir / name).read_bytes(), name


def test_full_artifact_tree_contains_no_config_secrets(tmp_path: Path) -> None:
    run_dir = write(tmp_path).run_dir
    for path in run_dir.iterdir():
        content = path.read_bytes()
        assert SECRET_API_KEY.encode() not in content, path.name
        assert SECRET_PASSWORD.encode() not in content, path.name


def test_serialization_failure_writes_nothing(tmp_path: Path) -> None:
    before = sorted(p.name for p in tmp_path.iterdir())
    bad = replace(
        make_inputs(),
        answers=(
            *make_inputs().answers,
            CapabilityAnswer(
                cap_id="CAP-OUT-02",
                status=CapabilityStatus.OK,
                elapsed_seconds=0.1,
                parsed={"probe": {1, 2}},
            ),
        ),
    )
    with pytest.raises(ValueError, match="not JSON-serializable"):
        write(tmp_path, bad)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_successful_write_leaves_no_temporary_files(tmp_path: Path) -> None:
    run_dir = write(tmp_path).run_dir
    assert [path.name for path in run_dir.iterdir() if path.name.endswith(".tmp")] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("variant", "../evil"),
        ("mode", ""),
        ("corpus_version", 0),
    ],
)
def test_invalid_identity_fields_fail_loudly(tmp_path: Path, field: str, value: object) -> None:
    with pytest.raises(ArtifactError, match=field):
        write(tmp_path, replace(make_inputs(), **{field: value}))


def test_naive_timestamps_and_inverted_range_fail_loudly(tmp_path: Path) -> None:
    naive = replace(make_inputs(), started_at=STARTED_AT.replace(tzinfo=None))
    with pytest.raises(ArtifactError, match="timezone-aware"):
        write(tmp_path, naive)
    inverted = replace(make_inputs(), started_at=FINISHED_AT, finished_at=STARTED_AT)
    with pytest.raises(ArtifactError, match="finished_at"):
        write(tmp_path, inverted)


def test_duplicate_cap_ids_and_bad_digest_fail_loudly(tmp_path: Path) -> None:
    inputs = make_inputs()
    duplicated = replace(inputs, answers=(*inputs.answers[:1], inputs.answers[0]))
    with pytest.raises(ArtifactError, match="unique"):
        write(tmp_path, duplicated)
    broken_stack = replace(inputs, stack=replace(inputs.stack, compose_sha256="nothex"))
    with pytest.raises(ArtifactError, match="compose_sha256"):
        write(tmp_path, broken_stack)
