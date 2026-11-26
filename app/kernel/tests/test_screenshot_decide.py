"""Which push regenerates the README's images, proven against real git history.

The decision moved out of the workflow shell so two traps have a test rather
than a comment. GitHub writes an editable pull request title into the merge
commit's body, so footer scanning must ignore merge commits: only a commit the
author wrote can ask for a capture. A changed-path list can outgrow a pipe
buffer; ``grep -q`` closes its producer early, and under ``pipefail`` the
producer's SIGPIPE becomes a false "no UI path" answer. The decision consumes
the complete list instead.

Every repository here is a throwaway fixture built in ``tmp_path``. The one
exception is the workflow test: it runs the decide step's real shell from
``screenshots.yml`` and asserts the run/reason output contract.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 - fixed argv invocations of git, bash and this script, no shell
from pathlib import Path
from typing import Any

import pytest
import yaml  # pyright: ignore[reportMissingTypeStubs]

from scripts.screenshots_decide import decide

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "screenshots.yml"
ZERO_SHA = "0" * 40

UI_PATHS = (
    "web/src/App.tsx",
    "app/capabilities/writing/web/i18n/en.json",
    "i18n/en.json",
    "scripts/screenshots.py",
    "scripts/screenshot_manifest.py",
)

SKIP_REASON = "no UI path changed and no regenerate override; skipping"


@pytest.fixture(autouse=True)
def _no_ambient_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide git's location variables while a hook or command spawns this suite.

    A leaked ``GIT_DIR`` points every fixture command — and the decision's own
    git reads — at the repository whose hook is running instead of the
    throwaway one in ``tmp_path``.
    """
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("git")
    assert executable is not None, "git is required to build the fixture repository"
    return subprocess.run(  # noqa: S603  # nosec  # fixed argv, no shell
        [executable, *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _repo_with_base(tmp_path: Path) -> tuple[Path, str]:
    repo = _init_repo(tmp_path)
    before = _commit(repo, {"README.md": "base\n"}, "chore: base")
    return repo, before


def _many(prefix: str, count: int, suffix: str) -> dict[str, str]:
    return {
        f"{prefix}/item-{index:04d}-with-a-deliberately-long-name{suffix}": ""
        for index in range(count)
    }


def test_a_docs_only_push_skips(tmp_path: Path) -> None:
    repo, before = _repo_with_base(tmp_path)
    after = _commit(repo, {"docs/guide.md": "installed\n"}, "docs: add a guide")

    assert decide("push", before, after, repo) == (False, SKIP_REASON)


@pytest.mark.parametrize("path", UI_PATHS, ids=lambda path: path)
def test_a_ui_relevant_push_regenerates(tmp_path: Path, path: str) -> None:
    repo, before = _repo_with_base(tmp_path)
    after = _commit(repo, {path: "changed\n"}, f"chore: touch {path}")

    assert decide("push", before, after, repo) == (True, "UI path changed: regenerate")


def test_a_regenerate_footer_on_a_normal_commit_wins(tmp_path: Path) -> None:
    repo, before = _repo_with_base(tmp_path)
    after = _commit(
        repo,
        {"docs/guide.md": "installed\n"},
        "docs: add a guide\n\nscreenshots: REGENERATE",
    )

    assert decide("push", before, after, repo) == (True, "override: regenerate requested")


def test_a_skip_footer_on_a_normal_commit_suppresses_a_docs_push(tmp_path: Path) -> None:
    repo, before = _repo_with_base(tmp_path)
    after = _commit(
        repo,
        {"docs/guide.md": "installed\n"},
        "docs: add a guide\n\nScreenshots: skip",
    )

    assert decide("push", before, after, repo) == (
        False,
        "override: skip requested and no UI path changed",
    )


def test_a_ui_path_still_wins_over_a_skip_footer(tmp_path: Path) -> None:
    repo, before = _repo_with_base(tmp_path)
    after = _commit(
        repo,
        {"i18n/en.json": "{}\n"},
        "docs: adjust a label\n\nScreenshots: skip",
    )

    assert decide("push", before, after, repo) == (True, "UI path changed: regenerate")


def test_a_footer_in_a_merge_commit_body_is_ignored(tmp_path: Path) -> None:
    repo, before = _repo_with_base(tmp_path)
    _git(repo, "checkout", "-b", "feature")
    _commit(repo, {"docs/feature.md": "feature\n"}, "docs: describe the feature")
    _git(repo, "checkout", "main")
    _git(
        repo,
        "merge",
        "--no-ff",
        "feature",
        "-m",
        "Merge pull request #7 from acme/feature",
        "-m",
        "Screenshots: regenerate",
    )
    merge = _git(repo, "rev-parse", "HEAD").stdout.strip()
    body = _git(repo, "log", "-1", "--format=%B").stdout
    assert "Screenshots: regenerate" in body

    assert decide("push", before, merge, repo) == (False, SKIP_REASON)


def test_a_footer_in_a_normal_commit_beside_a_merge_is_still_honored(tmp_path: Path) -> None:
    repo, before = _repo_with_base(tmp_path)
    _git(repo, "checkout", "-b", "feature")
    _commit(
        repo,
        {"docs/feature.md": "feature\n"},
        "docs: describe the feature\n\nScreenshots: regenerate",
    )
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", "feature", "-m", "Merge pull request #7 from acme/feature")
    merge = _git(repo, "rev-parse", "HEAD").stdout.strip()

    assert decide("push", before, merge, repo) == (True, "override: regenerate requested")


@pytest.mark.parametrize("before", ["", ZERO_SHA], ids=["empty", "all-zero"])
def test_a_first_push_regenerates(tmp_path: Path, before: str) -> None:
    repo, _ = _repo_with_base(tmp_path)
    after = _git(repo, "rev-parse", "HEAD").stdout.strip()

    assert decide("push", before, after, repo) == (True, "first push: regenerate")


@pytest.mark.parametrize("event", ["workflow_dispatch", "schedule"])
def test_manual_and_schedule_runs_always_regenerate(tmp_path: Path, event: str) -> None:
    assert decide(event, ZERO_SHA, ZERO_SHA, tmp_path) == (
        True,
        f"{event}: always regenerate",
    )


def test_a_large_docs_path_list_stays_quiet(tmp_path: Path) -> None:
    repo, before = _repo_with_base(tmp_path)
    after = _commit(
        repo,
        _many("docs/generated/notes", 1_100, ".md"),
        "docs: add generated notes",
    )
    names = _git(repo, "diff", "--name-only", before, after).stdout
    assert len(names.encode("utf-8")) > 65_536, "the fixture must outgrow a 64 KiB pipe buffer"

    assert decide("push", before, after, repo) == (False, SKIP_REASON)


def test_a_large_ui_path_list_still_regenerates(tmp_path: Path) -> None:
    repo, before = _repo_with_base(tmp_path)
    after = _commit(
        repo,
        _many("web/generated/screenshots", 1_100, ".txt"),
        "chore: add generated screenshots",
    )
    names = _git(repo, "diff", "--name-only", before, after).stdout
    assert len(names.encode("utf-8")) > 65_536, "the fixture must outgrow a 64 KiB pipe buffer"

    assert decide("push", before, after, repo) == (True, "UI path changed: regenerate")


def _step_script(job: str, name: str) -> str:
    workflow: Any = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = workflow["jobs"][job]["steps"]
    for step in steps:
        if step.get("name") == name:
            script = step.get("run")
            assert isinstance(script, str), f"step {name!r} has no shell script"
            return script
    raise AssertionError(f"no step {name!r} in job {job!r}")


@pytest.mark.parametrize(
    ("path", "expected"),
    [("docs/guide.md", "run=false"), ("web/src/App.tsx", "run=true")],
    ids=["docs-only", "ui"],
)
def test_the_workflow_decide_step_writes_run_and_reason_through_the_cli(
    tmp_path: Path,
    path: str,
    expected: str,
) -> None:
    repo, before = _repo_with_base(tmp_path)
    after = _commit(repo, {path: "changed\n"}, f"chore: touch {path}")
    output = tmp_path / "github-output"
    output.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "EVENT": "push",
        "BEFORE": before,
        "SHA": after,
        "GITHUB_OUTPUT": str(output),
        "PYTHONPATH": str(ROOT),
    }
    bash = shutil.which("bash")
    assert bash is not None, "bash is required to run the workflow step"

    subprocess.run(  # noqa: S603  # nosec  # fixed argv, trusted workflow script
        [bash, "-c", _step_script("decide", "Decide whether to regenerate")],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    lines = output.read_text(encoding="utf-8").splitlines()
    assert expected in lines
    reasons = [line for line in lines if line.startswith("reason=")]
    assert len(reasons) == 1, reasons
    assert reasons[0] != "reason="


def test_the_workflow_decide_step_delegates_history_reads_to_the_cli() -> None:
    script = _step_script("decide", "Decide whether to regenerate")

    assert "python3 -m scripts.screenshots_decide" in script
    assert "git log" not in script
