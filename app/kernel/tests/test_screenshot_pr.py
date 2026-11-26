"""A repeated screenshot run defers to the update PR that is already open.

Regeneration is deterministic: an unmerged screenshot PR holds exactly the
diff a later scheduled or manual run would produce again. The lookup therefore
asks GitHub for open ``chore/screenshots-*`` PRs against ``main`` and returns
the oldest one, and the workflow checks it after a real staged diff exists but
before it creates a branch. The fake ``gh`` here records its arguments and
token, so the query contract is asserted, not assumed.
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


@pytest.fixture(autouse=True)
def _no_ambient_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a leaked ``GIT_DIR`` from pointing fixture commits at another repo."""
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)


def _fake_gh(tmp_path: Path, payload: list[dict[str, Any]]) -> tuple[Path, Path, Path]:
    """A ``gh`` that answers ``pr list`` and records argv plus ``GH_TOKEN``."""
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


def test_the_workflow_defers_to_an_open_pr_before_creating_a_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [{"number": 42, "headRefName": "chore/screenshots-1234", "isCrossRepository": False}]
    bin_dir, args_file, token_file = _fake_gh(tmp_path, payload)
    _use_fake_gh(monkeypatch, bin_dir, args_file, token_file)

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

    script = _step_script("screenshots", "Open pull request if images changed")
    pending_at = script.index("python3 -m scripts.screenshots_pr")
    assert script.index("git diff --cached --quiet") < pending_at
    assert pending_at < script.index("git checkout -b")
    assert pending_at < script.index('git push "https://')
    assert "--force" not in script

    env = {
        **os.environ,
        "GITHUB_TOKEN": "token-123",
        "GH_TOKEN": "token-123",
        "REPOSITORY": "acme/narrare",
        "RUN_ID": "777",
        "PYTHONPATH": str(ROOT),
        "FAKE_GH_ARGS": str(args_file),
        "FAKE_GH_TOKEN": str(token_file),
    }
    bash = shutil.which("bash")
    assert bash is not None, "bash is required to run the workflow step"

    completed = subprocess.run(  # noqa: S603  # nosec  # fixed argv, trusted workflow script
        [bash, "-c", script],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "already open" in completed.stdout
    assert "#42" in completed.stdout
    assert _git(repo, "branch", "--show-current").stdout.strip() == "main"
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert "chore/screenshots-777" not in _git(repo, "branch", "--list").stdout
    args = _args(args_file)
    assert args[:2] == ["pr", "list"]
    assert args[args.index("--base") + 1] == "main"
    assert token_file.read_text(encoding="utf-8") == "token-123"
