"""A repeated screenshot run defers to an update PR that is already open.

A pending screenshot PR may already carry a later run's result, so opening a
second PR adds review work; it may also be stale after newer UI changes, and a
human must close or replace it when the newer captured diff matters. The lookup
asks GitHub for open ``chore/screenshots-*`` PRs against ``main`` and
returns the oldest one, and the workflow checks it after a real staged diff
exists but before it creates a branch. The fake ``gh`` records its latest
arguments and token, so the final query/creation call is asserted.

The publish step is executed for real against a throwaway repository. The
``pending=none`` case pushes to a local bare remote, so the branch, commit,
push and PR creation path is proven without network access. Malformed lookup
output cases run the same step and prove it stops before any branch exists.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - fixed argv invocations of git, bash and this module, no shell
from pathlib import Path
from typing import Any

import pytest
import yaml  # pyright: ignore[reportMissingTypeStubs]

from scripts.screenshots_pr import pending_screenshot_pr

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "screenshots.yml"
PUSH_URL = "https://x-access-token:token-123@github.com/acme/narrare.git"
BRANCH = "chore/screenshots-777"


@pytest.fixture(autouse=True)
def _no_ambient_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a leaked ``GIT_DIR`` from pointing fixture commits at another repo."""
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)


def _fake_gh(tmp_path: Path, payload: list[dict[str, Any]]) -> tuple[Path, Path, Path]:
    """A ``gh`` that answers every call and records the latest argv and token."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    args_file = tmp_path / "gh-args"
    token_file = tmp_path / "gh-token"
    script = bin_dir / "gh"
    script.write_text(
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$@" > "$FAKE_GH_ARGS"\n'
        'printf \'%s\' "${GH_TOKEN-}" > "$FAKE_GH_TOKEN"\n'
        "cat <<'JSON'\n"
        f"{json.dumps(payload)}\n"
        "JSON\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir, args_file, token_file


def _use_fake_gh(
    monkeypatch: pytest.MonkeyPatch,
    bin_dir: Path,
    args_file: Path,
    token_file: Path,
) -> None:
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_GH_ARGS", str(args_file))
    monkeypatch.setenv("FAKE_GH_TOKEN", str(token_file))


def _args(args_file: Path) -> list[str]:
    return args_file.read_text(encoding="utf-8").splitlines()


def test_no_open_screenshot_pr_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir, args_file, token_file = _fake_gh(tmp_path, [])
    _use_fake_gh(monkeypatch, bin_dir, args_file, token_file)

    assert pending_screenshot_pr("acme/narrare", "token-123") is None

    args = _args(args_file)
    assert args[:2] == ["pr", "list"]
    assert args[args.index("--repo") + 1] == "acme/narrare"
    assert args[args.index("--base") + 1] == "main"
    assert args[args.index("--state") + 1] == "open"
    assert "headRefName" in args[args.index("--json") + 1]
    assert token_file.read_text(encoding="utf-8") == "token-123"


def test_one_open_screenshot_pr_returns_its_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [{"number": 42, "headRefName": "chore/screenshots-1234", "isCrossRepository": False}]
    bin_dir, args_file, token_file = _fake_gh(tmp_path, payload)
    _use_fake_gh(monkeypatch, bin_dir, args_file, token_file)

    assert pending_screenshot_pr("acme/narrare", "token-123") == 42


def test_multiple_open_screenshot_prs_return_the_oldest_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        {"number": 57, "headRefName": "chore/screenshots-222", "isCrossRepository": False},
        {"number": 9, "headRefName": "feature/unrelated", "isCrossRepository": False},
        {"number": 42, "headRefName": "chore/screenshots-111", "isCrossRepository": False},
        {"number": 3, "headRefName": "chore/screenshots-fork", "isCrossRepository": True},
    ]
    bin_dir, args_file, token_file = _fake_gh(tmp_path, payload)
    _use_fake_gh(monkeypatch, bin_dir, args_file, token_file)

    assert pending_screenshot_pr("acme/narrare", "token-123") == 42


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
    )


def _step_script(job: str, name: str) -> str:
    workflow: Any = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = workflow["jobs"][job]["steps"]
    for step in steps:
        if step.get("name") == name:
            script = step.get("run")
            assert isinstance(script, str), f"step {name!r} has no shell script"
            return script
    raise AssertionError(f"no step {name!r} in job {job!r}")


def _publish_repo(tmp_path: Path, *, remote: Path | None = None) -> Path:
    """A repository with a staged screenshot diff, as the step receives it."""
    repo = tmp_path / "repo"
    (repo / "assets" / "screenshots").mkdir(parents=True)
    (repo / "docs" / "screenshots").mkdir(parents=True)
    (repo / "assets" / "screenshots" / "20-workspace.png").write_bytes(b"old")
    (repo / "docs" / "screenshots" / "README.md").write_text("old\n", encoding="utf-8")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "chore: base")
    (repo / "assets" / "screenshots" / "20-workspace.png").write_bytes(b"new")
    (repo / "docs" / "screenshots" / "README.md").write_text("new\n", encoding="utf-8")
    if remote is not None:
        remote.mkdir()
        _git(remote, "init", "--bare", "-b", "main")
        _git(repo, "config", "--add", f"url.file://{remote}.insteadOf", PUSH_URL)
        configured = _git(repo, "config", "--get", f"url.file://{remote}.insteadOf")
        assert configured.stdout.strip() == PUSH_URL
    return repo


def _publish_env(
    *,
    args_file: Path,
    token_file: Path,
    pythonpath: str = str(ROOT),
) -> dict[str, str]:
    return {
        **os.environ,
        "GITHUB_TOKEN": "token-123",
        "GH_TOKEN": "token-123",
        "REPOSITORY": "acme/narrare",
        "RUN_ID": "777",
        "PYTHONPATH": pythonpath,
        "FAKE_GH_ARGS": str(args_file),
        "FAKE_GH_TOKEN": str(token_file),
        "GIT_TERMINAL_PROMPT": "0",
    }


def _run_publish_step(
    repo: Path,
    env: dict[str, str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    script = _step_script("screenshots", "Open pull request if images changed")
    bash = shutil.which("bash")
    assert bash is not None, "bash is required to run the workflow step"
    return subprocess.run(  # noqa: S603  # nosec  # fixed argv, trusted workflow script
        [bash, "-c", script],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def _assert_publish_script_order() -> None:
    script = _step_script("screenshots", "Open pull request if images changed")
    pending_at = script.index("python3 -m scripts.screenshots_pr")
    assert script.index("git diff --cached --quiet") < pending_at
    assert pending_at < script.index("git checkout -b")
    assert pending_at < script.index('git push "https://')
    assert "--force" not in script


def _assert_no_branch(repo: Path, remote: Path) -> None:
    assert _git(repo, "branch", "--show-current").stdout.strip() == "main"
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert _git(repo, "config", "user.name").stdout.strip() == "Test"
    assert BRANCH not in _git(repo, "branch", "--list").stdout
    assert BRANCH not in _git(repo, "--git-dir", str(remote), "branch", "--list").stdout


def test_the_workflow_defers_to_an_open_pr_before_creating_a_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [{"number": 42, "headRefName": "chore/screenshots-1234", "isCrossRepository": False}]
    bin_dir, args_file, token_file = _fake_gh(tmp_path, payload)
    _use_fake_gh(monkeypatch, bin_dir, args_file, token_file)
    _assert_publish_script_order()

    remote = tmp_path / "remote.git"
    repo = _publish_repo(tmp_path, remote=remote)
    completed = _run_publish_step(
        repo,
        _publish_env(args_file=args_file, token_file=token_file),
    )

    assert "already open" in completed.stdout
    assert "#42" in completed.stdout
    _assert_no_branch(repo, remote)
    args = _args(args_file)
    assert args[:2] == ["pr", "list"]
    assert args[args.index("--base") + 1] == "main"
    assert token_file.read_text(encoding="utf-8") == "token-123"


def test_the_workflow_publishes_when_no_screenshot_pr_is_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir, args_file, token_file = _fake_gh(tmp_path, [])
    _use_fake_gh(monkeypatch, bin_dir, args_file, token_file)
    _assert_publish_script_order()

    remote = tmp_path / "remote.git"
    repo = _publish_repo(tmp_path, remote=remote)
    _run_publish_step(
        repo,
        _publish_env(args_file=args_file, token_file=token_file),
    )

    assert _git(repo, "branch", "--show-current").stdout.strip() == BRANCH
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "2"
    pushed = _git(repo, "--git-dir", str(remote), "rev-parse", f"refs/heads/{BRANCH}")
    assert pushed.stdout.strip() == _git(repo, "rev-parse", "HEAD").stdout.strip()
    subject = _git(repo, "--git-dir", str(remote), "log", "-1", "--format=%s", BRANCH)
    assert subject.stdout.strip() == "chore(screenshots): regenerate README images"

    # The final call is PR creation: the step passed the lookup and published.
    args = _args(args_file)
    assert args[:2] == ["pr", "create"]
    assert args[args.index("--base") + 1] == "main"
    assert args[args.index("--head") + 1] == BRANCH
    assert token_file.read_text(encoding="utf-8") == "token-123"


@pytest.mark.parametrize(
    "lookup_output",
    [
        "",
        "warning: gh printed a warning on stdout\n",
        "pending=abc\n",
        "pending=\n",
        "pending=12abc\n",
        "pending=0\n",
    ],
    ids=[
        "empty-stdout",
        "warning-text",
        "non-numeric-value",
        "empty-value",
        "trailing-text",
        "zero-number",
    ],
)
def test_the_workflow_fails_before_branching_on_malformed_lookup_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lookup_output: str,
) -> None:
    bin_dir, args_file, token_file = _fake_gh(tmp_path, [])
    _use_fake_gh(monkeypatch, bin_dir, args_file, token_file)

    # Shadow the real CLI with one that emits the malformed sentinel; the
    # workflow step itself is the real one from screenshots.yml.
    lookup = tmp_path / "lookup"
    (lookup / "scripts").mkdir(parents=True)
    (lookup / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (lookup / "scripts" / "screenshots_pr.py").write_text(
        f"import sys\nsys.stdout.write({lookup_output!r})\n",
        encoding="utf-8",
    )

    remote = tmp_path / "remote.git"
    repo = _publish_repo(tmp_path, remote=remote)
    completed = _run_publish_step(
        repo,
        _publish_env(
            args_file=args_file,
            token_file=token_file,
            pythonpath=f"{lookup}{os.pathsep}{ROOT}",
        ),
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "::error::" in output
    assert "unexpected value" in output
    assert "pending=none" in output
    assert "pending=<positive number>" in output
    if lookup_output:
        assert lookup_output.strip() in output
    _assert_no_branch(repo, remote)
    assert not args_file.exists(), "the workflow must fail before calling gh"
