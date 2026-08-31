"""Unit tests for the runner-adjacent seams (plan Task 15).

Failure-artifact writer, stack-facts assembly, api-version payload
shape guards, the CLI parser, and the production defaults of
``RunnerDeps``. Split from ``test_runner.py`` per RULE-04 (the wiring
sequence tests live there; these pin the individual seams).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from benchmark.__main__ import build_parser
from benchmark.ingest_events import IngestEvent
from benchmark.runner import DEFAULT_OUT_DIR, RunnerDeps
from benchmark.runner_failure import RunFailure, write_failure_artifacts
from benchmark.runner_stackfacts import api_version_payload, stack_facts
from benchmark.tests.runner_helpers import COMPOSE_SHA256, FINISHED_AT, STARTED_AT

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Failure-artifact writer
# ---------------------------------------------------------------------------


def _failure(stage: str = "ingest") -> RunFailure:
    return RunFailure(
        variant="light",
        mode="incremental",
        started_at=STARTED_AT,
        failed_at=FINISHED_AT,
        stage=stage,
        error_type="IngestError",
        error_message="ingest step 'extract' failed: HTTP 500: down",
        keep_stack=False,
        event_count=1,
    )


def test_failure_writer_writes_failure_json_and_events_jsonl(tmp_path: Path) -> None:
    event = IngestEvent(
        step="create_novel",
        chapter_stem=None,
        method="POST",
        path="/api/v1/novels",
        status=201,
        elapsed_seconds=0.1,
        request_body=None,
        response_body={"id": "novel-1"},
    )

    run_dir = write_failure_artifacts(tmp_path, _failure(), (event,))

    assert run_dir.name == f"{STARTED_AT.date().isoformat()}-light-failed-1"
    document = json.loads((run_dir / "failure.json").read_text(encoding="utf-8"))
    assert document["stage"] == "ingest"
    assert document["error"] == {
        "type": "IngestError",
        "message": "ingest step 'extract' failed: HTTP 500: down",
    }
    assert document["variant"] == "light" and document["keep_stack"] is False
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["step"] == "create_novel"


def test_failure_writer_increments_the_failed_run_counter(tmp_path: Path) -> None:
    first = write_failure_artifacts(tmp_path, _failure(), ())
    second = write_failure_artifacts(tmp_path, _failure(stage="scoring"), ())

    assert first.name.endswith("-failed-1")
    assert second.name.endswith("-failed-2")


# ---------------------------------------------------------------------------
# Stack facts + api version
# ---------------------------------------------------------------------------


class StubStack:
    def facts(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        return COMPOSE_SHA256, (("api", "sha256:abc"),)


class StubClient:
    def __init__(self, body: object) -> None:
        self._body = body

    def request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: object = None,
        headers: object = None,
    ) -> httpx.Response:
        assert method == "GET" and path == "/openapi.json"
        return httpx.Response(200, json=self._body)


def test_stack_facts_assembles_the_manifest_record() -> None:
    facts = stack_facts(StubStack(), StubClient({"info": {"version": "1.2.3"}}))

    assert facts.compose_sha256 == COMPOSE_SHA256
    assert facts.image_digests == (("api", "sha256:abc"),)
    assert facts.api_version == {"source": "GET /openapi.json info.version", "version": "1.2.3"}


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ({"nope": {}}, "info"),
        ({"info": {}}, "version"),
        ({"info": {"version": 3}}, "string"),
    ],
)
def test_api_version_shape_drift_fails_loudly(body: object, fragment: str) -> None:
    with pytest.raises(RuntimeError, match=fragment):
        api_version_payload(StubClient(body))


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def test_cli_parses_run_flags_and_defaults() -> None:
    from benchmark.config_schemas import CONFIG_PATH

    args = build_parser().parse_args(
        ["run", "--variant", "light", "--capabilities", "CAP-IN-01, CAP-OUT-01"]
    )

    assert args.command == "run"
    assert args.variant == "light"
    assert args.mode == "incremental"
    assert args.keep_stack is False
    assert args.capabilities == "CAP-IN-01, CAP-OUT-01"
    assert args.out == DEFAULT_OUT_DIR
    assert args.config == CONFIG_PATH


def test_cli_parses_explicit_run_flags() -> None:
    args = build_parser().parse_args(
        [
            "run",
            "--variant",
            "clean",
            "--mode",
            "import",
            "--keep-stack",
            "--out",
            "/var/narrare-runs",
            "--config",
            "/var/narrare-config.yaml",
        ]
    )

    assert args.mode == "import"
    assert args.keep_stack is True
    assert args.out.as_posix() == "/var/narrare-runs"
    assert args.config.as_posix() == "/var/narrare-config.yaml"


def test_cli_parses_stack_subcommand() -> None:
    for action in ("up", "down", "status"):
        args = build_parser().parse_args(["stack", action])
        assert args.command == "stack" and args.action == action


# ---------------------------------------------------------------------------
# RunnerDeps production defaults sanity
# ---------------------------------------------------------------------------


def test_default_deps_wire_production_collaborators() -> None:
    from benchmark.artifacts import current_git_commit, write_run_artifacts
    from benchmark.corpus_loader import load_corpus
    from benchmark.ingest import ingest
    from benchmark.provision import provision
    from benchmark.runner import default_driver_for, utc_now
    from benchmark.runner_failure import write_failure_artifacts as failure_writer

    deps = RunnerDeps()

    assert deps.provision_fn is provision
    assert deps.load_corpus_fn is load_corpus
    assert deps.ingest_fn is ingest
    assert deps.write_artifacts_fn is write_run_artifacts
    assert deps.write_failure_fn is failure_writer
    assert deps.git_commit_fn is current_git_commit
    assert deps.clock is utc_now
    assert deps.driver_for_fn is default_driver_for
    assert deps.ingest_sleeper.__module__ == "time"
    assert deps.corpus_root.name == "corpus"
