"""Regression tests for scripts/check_commit_message.py.

The `commit-msg` gate must work from a linked git worktree, where `.git` is a
*file* (the `gitdir:` pointer) rather than a directory. Reading the message from
the cwd-relative `.git/COMMIT_EDITMSG` silently fails there, so the script must
resolve the real path through git.

The regression cases below therefore build a genuine worktree shape (a tmp
repository plus `git worktree add`) and invoke the script exactly as git does:
as a subprocess from the worktree root, with no arguments and an empty stdin.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import scripts.check_commit_message as check_commit_message
from scripts.check_commit_message import check_message, read_commit_message

if TYPE_CHECKING:
    import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _ROOT / "scripts" / "check_commit_message.py"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``cwd`` and fail loudly if it does not succeed."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _worktree_with_commit_message(tmp_path: Path) -> tuple[Path, Path]:
    """Create a linked worktree; return (worktree_root, commit_message_path).

    The worktree's `.git` is asserted to be a file, because that is the shape the
    defect depends on: the cwd-relative `.git/COMMIT_EDITMSG` does not exist.
    """
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-b", "main", cwd=main)
    _git("config", "user.email", "test@example.com", cwd=main)
    _git("config", "user.name", "Test User", cwd=main)
    _git("config", "commit.gpgsign", "false", cwd=main)
    (main / "README.md").write_text("hello\n", encoding="utf-8")
    _git("add", "README.md", cwd=main)
    _git("commit", "-m", "chore: initial commit", cwd=main)

    worktree = tmp_path / "worktree"
    _git("worktree", "add", "-b", "worktree-branch", str(worktree), cwd=main)

    assert (worktree / ".git").is_file(), "linked worktree .git must be a file"
    assert not (worktree / ".git" / "COMMIT_EDITMSG").exists()

    raw = _git("rev-parse", "--git-path", "COMMIT_EDITMSG", cwd=worktree).stdout.strip()
    msg_path = Path(raw)
    if not msg_path.is_absolute():
        msg_path = worktree / msg_path
    return worktree, msg_path


def _run_script_from(
    worktree: Path, stdin_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the checker as git invokes it, from the worktree root.

    ``stdin_text=None`` emulates pre-commit's empty, non-interactive stdin
    (``DEVNULL``); a string pipes that message on stdin instead.
    """
    cmd = [sys.executable, str(_SCRIPT)]
    if stdin_text is None:
        return subprocess.run(
            cmd,
            cwd=worktree,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
    return subprocess.run(
        cmd,
        cwd=worktree,
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )


class _TtyStdin(io.StringIO):
    """A TTY-like stdin whose ``read()`` must never be called."""

    def isatty(self) -> bool:
        return True

    def read(self, *args: object, **kwargs: object) -> str:
        raise AssertionError("stdin must not be read when it is a TTY")


def test_valid_message_in_worktree_commit_editmsg_is_accepted(tmp_path: Path) -> None:
    """A valid Conventional Commits message in a worktree must exit 0."""
    worktree, msg_path = _worktree_with_commit_message(tmp_path)
    msg_path.write_text(
        "feat(scripts): resolve the commit-message path\n",
        encoding="utf-8",
    )

    result = _run_script_from(worktree)

    assert result.returncode == 0, result.stdout + result.stderr


def test_invalid_message_in_worktree_commit_editmsg_is_rejected(tmp_path: Path) -> None:
    """An invalid subject in a worktree must still exit 1 (no false accept)."""
    worktree, msg_path = _worktree_with_commit_message(tmp_path)
    msg_path.write_text("Bad subject\n", encoding="utf-8")

    result = _run_script_from(worktree)

    assert result.returncode == 1, result.stdout + result.stderr


def test_piped_message_overrides_stale_commit_editmsg(tmp_path: Path) -> None:
    """A message piped on stdin wins over a stale COMMIT_EDITMSG (just recipe).

    `just check-commit-msg "<msg>"` feeds the candidate on stdin while a valid
    leftover sits in the repo's COMMIT_EDITMSG. Resolving the git path first
    would validate the stale file and accept an invalid piped message.
    """
    worktree, msg_path = _worktree_with_commit_message(tmp_path)
    msg_path.write_text("feat(scripts): stale leftover message\n", encoding="utf-8")

    result = _run_script_from(worktree, stdin_text="Bad subject\n")

    assert result.returncode == 1, result.stdout + result.stderr


def test_check_message_still_rejects_empty_message() -> None:
    """The pure validator keeps its behaviour (guard against a weakened fix)."""
    assert check_message("") == ["Empty commit message"]


def test_read_commit_message_prefers_explicit_argv_path(tmp_path: Path) -> None:
    """Git's own commit-msg argument is the first resolution source."""
    explicit = tmp_path / "COMMIT_EDITMSG"
    explicit.write_text("feat(core): explicit path\n", encoding="utf-8")

    message = read_commit_message([str(explicit)], stdin=io.StringIO("chore: stdin\n"))

    assert message == "feat(core): explicit path\n"


def test_read_commit_message_resolves_git_path_without_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With an empty (non-TTY) stdin the message comes from git's path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    raw = _git("rev-parse", "--git-path", "COMMIT_EDITMSG", cwd=repo).stdout.strip()
    msg_path = Path(raw)
    if not msg_path.is_absolute():
        msg_path = repo / msg_path
    msg_path.write_text("fix(api): via git\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    message = read_commit_message([], stdin=io.StringIO(""))

    assert message == "fix(api): via git\n"


def test_read_commit_message_prefers_piped_stdin_over_git_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-empty piped message outranks an existing COMMIT_EDITMSG."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    raw = _git("rev-parse", "--git-path", "COMMIT_EDITMSG", cwd=repo).stdout.strip()
    msg_path = Path(raw)
    if not msg_path.is_absolute():
        msg_path = repo / msg_path
    msg_path.write_text("feat(scripts): stale leftover message\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    message = read_commit_message([], stdin=io.StringIO("Bad subject\n"))

    assert message == "Bad subject\n"


def test_read_commit_message_skips_stdin_when_tty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interactive (TTY) stdin must never be read; git's path is used."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    raw = _git("rev-parse", "--git-path", "COMMIT_EDITMSG", cwd=repo).stdout.strip()
    msg_path = Path(raw)
    if not msg_path.is_absolute():
        msg_path = repo / msg_path
    msg_path.write_text("feat(core): from git path\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    message = read_commit_message([], stdin=_TtyStdin("chore: must be ignored\n"))

    assert message == "feat(core): from git path\n"


def test_read_commit_message_reports_git_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failing git call is reported on stderr, never swallowed (RULE-11)."""

    def _failing_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=128, cmd=["git"])

    monkeypatch.setattr(check_commit_message.subprocess, "run", _failing_git)

    message = read_commit_message([], stdin=io.StringIO(""))

    captured = capsys.readouterr()
    assert message == ""
    assert "Could not resolve COMMIT_EDITMSG via git" in captured.err
