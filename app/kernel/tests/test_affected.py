"""The resolver's contract: one answer per set of changed paths, and every
fallback says why. Mapping tests pin the path tables against a fixed
capability set — the real checkout's directories are never the subject,
with one exception: a single test asserts the real checkout's six suites,
guarding the discovery rule itself — while the git-backed tests and every
CLI mode run against a miniature repository built in tmp_path, so the
fixture, not Narrare, is what changes.
"""

import json
import os
import shutil
import subprocess  # nosec B404 - fixed argv invocations of git and this script, no shell
import sys
from pathlib import Path

import pytest

from scripts import affected
from scripts.affected import changed, default_base, known_capabilities, resolve

# The checkout's own root — scripts/ sits directly under it — for the one
# test where the real directories, not the fixture's, are the subject.
REPO_ROOT = Path(affected.__file__).resolve().parent.parent

FIXTURE_CAPABILITIES = ("chat", "writing")


@pytest.fixture(autouse=True)
def _capability_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the capability set to the fixture's two suites.

    The tests stand in tmp_path, where a miniature app/capabilities tree
    holds exactly chat and writing as suites, plus notes — a capability
    directory with tests but no e2e/, so discovery must skip it — so the
    mapping tests pass whether or not Narrare itself is present; the real
    checkout's directories are never the subject. The git-backed fixtures
    chdir further, into their repo.
    """
    for name in FIXTURE_CAPABILITIES:
        (tmp_path / "app" / "capabilities" / name / "e2e").mkdir(parents=True)
    (tmp_path / "app" / "capabilities" / "notes" / "tests").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def _no_ambient_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide git's location variables from the test process itself.

    Git exports GIT_DIR (and, in some versions, GIT_INDEX_FILE) while it
    runs hooks, and the pre-push hook runs this suite: with a leaked
    GIT_DIR, git resolves every call — the fixtures', and the resolver's
    in-process ones — to the repository whose hook is running instead of
    the miniature one in tmp_path.
    """
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)


def _git(repo: Path, *args: str) -> None:
    executable = shutil.which("git")
    assert executable is not None, "git is required to build the fixture repository"
    subprocess.run([executable, *args], cwd=repo, check=True, capture_output=True)  # noqa: S603


def _make_repo(tmp_path: Path, *, remote: bool, ahead: bool) -> Path:
    """A miniature Narrare: two capability suites, one commit past the base."""
    repo = tmp_path / "narrare"
    for directory in (
        "app/capabilities/chat/e2e",
        "app/capabilities/writing/e2e",
        "app/kernel",
        "i18n",
        "web",
    ):
        (repo / directory).mkdir(parents=True)
    (repo / "app/capabilities/chat/e2e/test_chat.py").write_text("", encoding="utf-8")
    (repo / "app/capabilities/writing/e2e/test_writing.py").write_text("", encoding="utf-8")
    (repo / "justfile").write_text("check:\n    echo ok\n", encoding="utf-8")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    if remote:
        _git(repo, "update-ref", "refs/remotes/narrare/main", "HEAD")
        _git(repo, "symbolic-ref", "refs/remotes/narrare/HEAD", "refs/remotes/narrare/main")
        _git(repo, "remote", "add", "narrare", str(tmp_path / "upstream"))
    if ahead:
        (repo / "app/capabilities/writing/x.py").write_text("", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "writing change")
    return repo


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """One committed change past narrare/main; the worktree is clean."""
    made = _make_repo(tmp_path, remote=True, ahead=True)
    monkeypatch.chdir(made)
    return made


@pytest.fixture
def repo_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HEAD sits exactly on narrare/main; nothing is touched."""
    made = _make_repo(tmp_path, remote=True, ahead=False)
    monkeypatch.chdir(made)
    return made


@pytest.fixture
def repo_without_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """No remote and no remote refs: no base can be resolved."""
    made = _make_repo(tmp_path, remote=False, ahead=False)
    monkeypatch.chdir(made)
    return made


def run(args: list[str], *, stderr: bool = False, cwd: Path | None = None) -> str:
    """Run the checkout's script as CI does, from a chosen working directory."""
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(Path(affected.__file__)), *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=cwd if cwd is not None else Path.cwd(),
    )
    output = completed.stderr if stderr else completed.stdout
    assert output is not None
    return output


def run_status(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the script without check=True: the exit status is the subject."""
    return subprocess.run(  # noqa: S603
        [sys.executable, str(Path(affected.__file__)), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_a_capability_path_owes_that_suite():
    assert resolve(["app/capabilities/writing/web/editor.tsx"]).capabilities == ["writing"]


def test_two_capabilities_are_sorted_and_deduplicated():
    r = resolve(
        ["app/capabilities/writing/a", "app/capabilities/chat/b", "app/capabilities/writing/c"]
    )
    assert r.capabilities == ["chat", "writing"]


def test_a_shared_surface_owes_every_suite():
    for path in (
        "web/vite.config.ts",
        "app/kernel/testing/stack.py",
        "i18n/de.json",
        "justfile",
        "uv.lock",
        "app/api/router.py",
        "app/generated/client.ts",
        "pyproject.toml",
        "pnpm-lock.yaml",
        ".github/workflows/ci.yml",
    ):
        assert resolve([path]).capabilities is None, path


def test_the_root_conftest_owes_every_suite():
    assert resolve(["app/conftest.py"]).capabilities is None


def test_the_capabilities_conftest_owes_every_suite():
    assert resolve(["app/capabilities/conftest.py"]).capabilities is None


def test_an_unknown_capability_dir_owes_every_suite():
    assert resolve(["app/capabilities/nope/e2e/test_x.py"]).capabilities is None


def test_a_capability_dir_without_e2e_is_not_a_suite():
    """`notes` has tests but no e2e/: discovery skips it, and a path under it
    is an unknown capability — the fail-open side."""
    assert "notes" not in known_capabilities()
    assert resolve(["app/capabilities/notes/x.py"]).capabilities is None


def test_the_real_checkout_discovers_its_six_suites(
    monkeypatch: pytest.MonkeyPatch,
):
    """The one test where the checkout's own directories are the subject: a
    fixture cannot see the discovery rule itself break."""
    monkeypatch.chdir(REPO_ROOT)
    assert known_capabilities() == {
        "chat",
        "knowledge",
        "prompts",
        "settings",
        "setup",
        "writing",
    }


def test_every_suite_with_no_nameable_suite_reddens_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Empty discovery (no e2e/ anywhere) must not print [] and exit 0: a
    nightly owes every suite by definition, so a green gate with no browser
    is the design's anti-goal. The script cannot do its job — exit 3."""
    broken = tmp_path / "broken"
    (broken / "app/capabilities/notes/tests").mkdir(parents=True)
    monkeypatch.chdir(broken)
    completed = run_status(["--all", "--json"])
    assert completed.returncode == 3
    assert "every suite is owed" in completed.stderr
    assert json.loads(completed.stdout) == []


def test_docs_and_tooling_owe_nothing():
    r = resolve(
        [
            "docs/x.md",
            "README.md",
            "scripts/affected.py",
            "docker-compose.dev.yml",
            ".pre-commit-config.yaml",
            "CHANGELOG.md",
            "LICENSE",
            "AGENTS.md",
            "CONTRIBUTING.md",
            "TESTING.md",
            ".release-please-manifest.json",
            ".github/dependabot.yml",
        ]
    )
    assert r.capabilities == []


def test_an_unknown_path_owes_every_suite():
    assert resolve(["newdir/thing.txt"]).capabilities is None


def test_a_release_pr_owes_nothing_even_for_a_lockfile():
    files = ["pyproject.toml", "uv.lock", "CHANGELOG.md"]
    assert resolve(files, release=True).capabilities == []
    assert resolve(files).capabilities is None  # without the flag: shared surface


def test_changed_lists_the_diff_against_the_base(repo: Path):
    assert changed("narrare/main", worktree=False) == ["app/capabilities/writing/x.py"]


def test_an_unreadable_base_is_not_an_empty_change(repo: Path):
    assert changed("no-such-ref", worktree=False) is None


def test_worktree_adds_uncommitted_and_untracked_paths(repo: Path):
    # commit one writing file; leave an untracked chat file uncommitted
    (repo / "app/capabilities/chat/y.py").write_text("", encoding="utf-8")
    assert changed("narrare/main", worktree=True) == [
        "app/capabilities/chat/y.py",
        "app/capabilities/writing/x.py",
    ]


def test_default_base_is_the_remote_default_branch(repo: Path):
    assert default_base() == "narrare/main"


def test_no_remote_means_no_base(repo_without_remote: Path):
    assert default_base() is None


def test_json_mode_prints_an_array_for_the_matrix(repo: Path):
    out = run(["--base", "narrare/main", "--json"])
    assert json.loads(out) == ["writing"]


def test_json_all_expands_to_every_capability(repo: Path):
    assert json.loads(run(["--all", "--json"])) == sorted(known_capabilities())


def test_json_none_prints_an_empty_array(repo: Path):
    assert json.loads(run(["--none", "--json"])) == []


def test_paths_mode_prints_suite_dirs(repo: Path):
    assert run(["--paths", "writing"]).split() == ["app/capabilities/writing/e2e/"]


def test_paths_all_prints_every_suite_and_says_so(repo: Path):
    expected = [f"app/capabilities/{name}/e2e/" for name in sorted(FIXTURE_CAPABILITIES)]
    assert run(["--paths", "all"]).split() == expected
    assert "scope all: every suite" in run(["--paths", "all"], stderr=True)


def test_a_subdirectory_still_sees_every_suite(repo: Path):
    """The every-suite fallback expands from the repo root, not from the cwd."""
    (repo / "app/kernel/stack.py").write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "shared change")
    here = repo / "app/kernel"
    assert json.loads(run(["--base", "narrare/main", "--json"], cwd=here)) == sorted(
        FIXTURE_CAPABILITIES
    )
    assert "all suites" in run(["--base", "narrare/main", "--json"], stderr=True, cwd=here)


def test_paths_affected_with_nothing_touched_prints_nothing(repo_clean: Path):
    assert run(["--paths", "affected"]).strip() == ""


def test_a_fallback_says_why_on_stderr(repo: Path):
    assert "all suites" in run(["--base", "no-such-ref", "--json"], stderr=True)
