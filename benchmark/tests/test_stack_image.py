"""Unit tests for app-image acquisition (rehearsal finding #2).

``StackManager.up()`` with ``stack.build_image: auto`` inspects the app
image locally and builds it from the repo Dockerfile when missing (no
GHCR release image exists yet — compose's pull-only default fails);
``never`` skips acquisition entirely; a failed build raises
``StackError`` with captured output. NO docker required: subprocess I/O
goes through a fake ``CommandRunner`` (``test_stack`` precedent). Split
from ``test_stack.py`` per RULE-04.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from benchmark.config import (
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    LlmConfig,
    RunConfig,
    StackConfig,
)
from benchmark.stack import (
    APP_IMAGE,
    REPO_ROOT,
    CommandResult,
    ImageSource,
    StackError,
    StackManager,
    ensure_image,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

PREFIX = "narrare-benchmark"
# Tail of the build argv — the FakeRunner matches command tails, and only
# ``docker build`` ends with the Dockerfile flag + repo-root context pair.
_BUILD_TAIL = ("-f", str(REPO_ROOT / "Dockerfile"), str(REPO_ROOT))


class FakeRunner:
    """Canned ``CommandRunner``: matches argv tails to ``(rc, out, err)``."""

    def __init__(
        self, responses: dict[tuple[str, ...], tuple[int, str, str]] | None = None
    ) -> None:
        self.responses: dict[tuple[str, ...], tuple[int, str, str]] = responses or {}
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> CommandResult:
        call = list(args)
        self.calls.append(call)
        for tail, (rc, out, err) in self.responses.items():
            if len(call) >= len(tail) and tuple(call[-len(tail) :]) == tail:
                return CommandResult(tuple(call), rc, out, err)
        return CommandResult(tuple(call), 0, "", "")


class AlwaysHealthy:
    """No-op probe — acquisition tests never reach health polling."""

    def healthy(self, base_url: str) -> bool:
        return base_url != ""


def make_config(*, build_image: str) -> BenchmarkConfig:
    return BenchmarkConfig(
        # mode="containers": image acquisition is a containers-mode-only
        # concern (PO ruling — hybrid never builds an image).
        stack=StackConfig(PREFIX, 18080, 18180, "containers", build_image),
        api=ApiConfig(None, 60.0),
        auth=AuthConfig("benchmark@example.com", "change-me-benchmark-password"),
        llm=LlmConfig("anthropic", "sk-test-dummy", "m", "http://localhost:11434", "general"),
        run=RunConfig(["clean"], ["incremental"], False, []),
    )


def make_manager(
    runner: FakeRunner, override_dir: Path, *, build_image: str = "auto"
) -> StackManager:
    return StackManager(
        make_config(build_image=build_image),
        runner=runner,
        probe=AlwaysHealthy(),
        port_selector=lambda low, high: 18080,
        override_dir=override_dir,
    )


@pytest.fixture()
def override_dir(tmp_path: Path) -> Path:
    return tmp_path / "stack-override"


class TestUpImageAcquisition:
    """``up()`` acquires the app image BEFORE compose up (finding #2)."""

    def test_auto_present_inspects_but_never_builds(self, override_dir: Path) -> None:
        runner = FakeRunner({("image", "inspect", APP_IMAGE): (0, "", "")})
        make_manager(runner, override_dir).up()
        (inspect_call,) = [c for c in runner.calls if c[:2] == ["docker", "image"]]
        assert inspect_call == ["docker", "image", "inspect", APP_IMAGE]
        assert [c for c in runner.calls if "build" in c] == []

    def test_auto_missing_builds_with_expected_args_before_up(self, override_dir: Path) -> None:
        runner = FakeRunner({("image", "inspect", APP_IMAGE): (1, "", "no-such-image")})
        make_manager(runner, override_dir).up()
        (build_call,) = [c for c in runner.calls if "build" in c]
        assert build_call == [
            "docker",
            "build",
            "-t",
            APP_IMAGE,
            "-f",
            str(REPO_ROOT / "Dockerfile"),
            str(REPO_ROOT),
        ]
        (up_index,) = [i for i, c in enumerate(runner.calls) if c[-2:] == ["up", "-d"]]
        assert runner.calls.index(build_call) < up_index

    def test_never_config_skips_inspect_and_build(self, override_dir: Path) -> None:
        runner = FakeRunner()
        make_manager(runner, override_dir, build_image="never").up()
        assert [c for c in runner.calls if c[:2] == ["docker", "image"]] == []
        assert [c for c in runner.calls if "build" in c] == []

    def test_build_failure_raises_stack_error_with_output(self, override_dir: Path) -> None:
        runner = FakeRunner(
            {
                ("image", "inspect", APP_IMAGE): (1, "", ""),
                _BUILD_TAIL: (1, "build-stdout", "build-stderr"),
            }
        )
        with pytest.raises(StackError, match="build-stderr") as excinfo:
            make_manager(runner, override_dir).up()
        assert "docker build failed" in str(excinfo.value)


class TestEnsureImage:
    def test_returns_local_present_when_inspect_succeeds(self) -> None:
        runner = FakeRunner({("image", "inspect", APP_IMAGE): (0, "", "")})
        assert ensure_image(APP_IMAGE, runner=runner) is ImageSource.LOCAL_PRESENT

    def test_returns_built_after_successful_build(self) -> None:
        runner = FakeRunner(
            {("image", "inspect", APP_IMAGE): (1, "", ""), _BUILD_TAIL: (0, "", "")}
        )
        assert ensure_image(APP_IMAGE, runner=runner) is ImageSource.BUILT

    def test_failed_build_raises_with_captured_output(self) -> None:
        runner = FakeRunner(
            {("image", "inspect", APP_IMAGE): (1, "", ""), _BUILD_TAIL: (1, "out", "err-line")}
        )
        with pytest.raises(StackError, match="err-line"):
            ensure_image(APP_IMAGE, runner=runner)
