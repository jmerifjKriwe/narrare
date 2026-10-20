"""Input-resolution tests for scripts/check_commit_message.py.

Split from `test_check_commit_message.py` (RULE-04): the claim gate and the
message resolution share one script, but these proofs need a real repository,
a pseudo-terminal, and their own helpers.

Resolution order under test: ``argv[1]`` → non-TTY stdin (authoritative, empty
included) → `git rev-parse --git-path COMMIT_EDITMSG` (TTY only) → ``""``.

The regression cases build a genuine worktree shape (a tmp repository plus
`git worktree add`) and invoke the script exactly as a manual terminal run
does: as a subprocess from the worktree root, with no arguments and a TTY
stdin. That is the only case in which the checker falls through to git's path
(a non-TTY stdin is authoritative even when empty, so it never reaches it).
"""

from __future__ import annotations

import io
import os
import pty
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import scripts.check_commit_message as checker

if TYPE_CHECKING:
    import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_commit_message.py"

_CLAIM = "User-visible: You can now import a project from a zip archive."


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
    """Run the checker as a manual terminal run does, from the worktree root.

    ``stdin_text=None`` attaches a real pseudo-terminal, so ``isatty()`` is
    true: only then does the checker fall through to git's path. A string pipes
    that message on a non-TTY stdin instead.
    """
    cmd = [sys.executable, str(_SCRIPT)]
    if stdin_text is None:
        master, slave = pty.openpty()
        try:
            return subprocess.run(
                cmd,
                cwd=worktree,
                stdin=slave,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            os.close(master)
            os.close(slave)
    return subprocess.run(
        cmd,
        cwd=worktree,
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_script_with_empty_stdin(worktree: Path) -> subprocess.CompletedProcess[str]:
    """Run the checker with the empty, non-TTY stdin of a non-interactive git run."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=worktree,
        stdin=subprocess.DEVNULL,
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
        f"feat(scripts): resolve the commit-message path\n\n{_CLAIM}\n",
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
    msg_path.write_text(
        f"feat(scripts): stale leftover message\n\n{_CLAIM}\n",
        encoding="utf-8",
    )

    result = _run_script_from(worktree, stdin_text="Bad subject\n")

    assert result.returncode == 1, result.stdout + result.stderr


def test_empty_non_tty_stdin_is_not_the_stale_commit_editmsg(tmp_path: Path) -> None:
    """Empty stdin must never fall through to a stale COMMIT_EDITMSG (#261).

    The worktree holds a *valid* leftover message. If empty non-TTY stdin were
    allowed to fall through, the checker would accept that stale message; the
    empty stream is authoritative, so the message is empty and rejected.
    """
    worktree, msg_path = _worktree_with_commit_message(tmp_path)
    msg_path.write_text(
        f"feat(scripts): stale leftover message\n\n{_CLAIM}\n",
        encoding="utf-8",
    )

    result = _run_script_with_empty_stdin(worktree)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Empty commit message" in result.stdout


def test_read_message_empty_non_tty_stdin_is_authoritative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty non-TTY stdin wins over git's path and yields ``""``.

    A stale COMMIT_EDITMSG exists in the repository; reading it here is the
    #261 stale-message path, so the empty stream must stay authoritative and
    `check_message` must reject the empty result.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    raw = _git("rev-parse", "--git-path", "COMMIT_EDITMSG", cwd=repo).stdout.strip()
    msg_path = Path(raw)
    if not msg_path.is_absolute():
        msg_path = repo / msg_path
    msg_path.write_text("fix(api): via git\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    message = checker.read_message([], stdin=io.StringIO(""))

    assert message == ""
    assert checker.check_message(message) == ["Empty commit message"]


def test_read_message_prefers_piped_stdin_over_git_path(
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

    message = checker.read_message([], stdin=io.StringIO("Bad subject\n"))

    assert message == "Bad subject\n"


def test_read_message_skips_stdin_when_tty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    message = checker.read_message([], stdin=_TtyStdin("chore: must be ignored\n"))

    assert message == "feat(core): from git path"


def test_read_message_reports_git_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failing git call is reported on stderr, never swallowed (RULE-11)."""

    def _failing_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=128, cmd=["git"])

    monkeypatch.setattr(checker.subprocess, "run", _failing_git)

    message = checker.read_message([], stdin=_TtyStdin(""))

    captured = capsys.readouterr()
    assert message == ""
    assert "Could not resolve COMMIT_EDITMSG via git" in captured.err
