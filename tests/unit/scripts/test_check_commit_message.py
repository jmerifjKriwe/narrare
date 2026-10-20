"""Unit and regression tests for scripts/check_commit_message.py.

Two concerns share this module:

* the commit-claim gate — `feat`/`fix` must state a `User-visible:` effect;
* the message-source order, at the level that needs no repository: `argv[1]`
  beats stdin, and comment lines are stripped from message files.

The repository-level resolution — the linked-worktree proof (where `.git` is a
*file*) and the TTY fall-through to `git rev-parse --git-path COMMIT_EDITMSG` —
lives in `test_check_commit_message_input_resolution.py` (RULE-04 split).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import scripts.check_commit_message as checker

if TYPE_CHECKING:
    import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_commit_message.py"


def _run(monkeypatch: pytest.MonkeyPatch, message: str) -> int:
    """Run the CLI on `message` as stdin (the CI / `just` path)."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(message))
    return checker.main([str(_SCRIPT)])


_CLAIM = "User-visible: You can now import a project from a zip archive."


# ── The claim rule ──────────────────────────────────────────────


def test_feat_without_claim_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """`feat` claims a user-facing change and must state it."""
    message = "feat(kb): wire the rerank tier into the context service"
    errors = checker.check_message(message)
    assert errors
    assert any("User-visible" in error for error in errors)
    assert any("chore(<scope>)" in error for error in errors)
    assert _run(monkeypatch, message + "\n") == 1


def test_feat_with_claim_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stated user-visible effect satisfies the gate."""
    message = f"feat(import): project import v1\n\n{_CLAIM}\n"
    assert checker.check_message(message) == []
    assert _run(monkeypatch, message) == 0


def test_fix_without_claim_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """`fix` bumps the patch version and is gated the same way."""
    message = "fix(gates): retire the phantom doc anchor"
    assert any("User-visible" in error for error in checker.check_message(message))
    assert _run(monkeypatch, message + "\n") == 1


def test_fix_with_claim_passes() -> None:
    message = f"fix(editor): keep the caret after an undo\n\n{_CLAIM}\n"
    assert checker.check_message(message) == []


def test_placeholder_claim_is_rejected() -> None:
    """A placeholder is not a claim."""
    for placeholder in ("n/a", "none", "tbd", "-"):
        message = f"feat(import): project import v1\n\nUser-visible: {placeholder}\n"
        errors = checker.check_message(message)
        assert errors, placeholder
        assert any("placeholder" in error for error in errors)


def test_short_claim_is_rejected() -> None:
    """The claim must carry at least 20 characters of value."""
    message = "feat(import): project import v1\n\nUser-visible: import\n"
    assert any("User-visible" in error for error in checker.check_message(message))


def test_internal_work_uses_chore_without_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Internal production code passes as `chore(<scope>)`, no claim needed."""
    message = "chore(kb): wire the rerank tier into the context service\n"
    assert checker.check_message(message) == []
    assert _run(monkeypatch, message) == 0


def test_claim_is_taken_from_the_body_not_the_subject() -> None:
    """A claim in the subject is not a body line (subject is capped at 100 chars)."""
    message = "feat(import): User-visible: You can now import a project from a zip\n"
    assert any("User-visible" in error for error in checker.check_message(message))


# ── PR path: title + body composition (the CI input) ────────────


def test_pr_title_and_body_composition_passes() -> None:
    """CI composes `<PR title>\\n\\n<PR body>`; the claim lives in the body."""
    title = "feat(import): project import v1"
    body = f"Adds the import wizard.\n\n{_CLAIM}\n\nCloses #236"
    assert checker.check_message(f"{title}\n\n{body}") == []


def test_pr_title_only_is_rejected() -> None:
    """A `feat` PR with an empty body cannot carry the claim."""
    assert checker.check_message("feat(import): project import v1\n\n\n") != []


def test_markdown_heading_in_body_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    """`#` is a Markdown heading in a PR body, not a git comment — keep it."""
    message = f"feat(import): project import v1\n\n# Import\n\n{_CLAIM}\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(message))
    assert checker.read_message([str(_SCRIPT)]) == message
    assert checker.check_message(message) == []


# ── Input resolution ────────────────────────────────────────────


def test_file_argument_wins_over_stdin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The pre-commit hook passes the message file; that must beat stdin."""
    hook_file = tmp_path / "COMMIT_EDITMSG"
    hook_file.write_text(f"feat(import): project import v1\n\n{_CLAIM}\n", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", io.StringIO("fix(gates): wrong message\n"))
    assert checker.read_message([str(_SCRIPT), str(hook_file)]).startswith("feat(import)")


def test_comment_lines_are_stripped_from_the_message_file(tmp_path: Path) -> None:
    """git's `#` comments belong to the message file only."""
    hook_file = tmp_path / "COMMIT_EDITMSG"
    hook_file.write_text(
        f"feat(import): project import v1\n\n# Please enter the commit message\n\n{_CLAIM}\n",
        encoding="utf-8",
    )
    message = checker.read_message([str(_SCRIPT), str(hook_file)])
    assert "# Please enter" not in message
    assert checker.check_message(message) == []


# ── Existing behaviour (regression) ─────────────────────────────


def test_merge_and_revert_subjects_pass() -> None:
    assert checker.check_message("Merge pull request #260 from x/y\n") == []
    assert checker.check_message('Revert "feat(import): project import v1"\n') == []


def test_uppercase_description_is_rejected() -> None:
    errors = checker.check_message("docs: Update the deployment guide\n")
    assert errors
    assert any("lowercase" in error for error in errors)


def test_unknown_type_is_rejected_with_chore_hint() -> None:
    errors = checker.check_message("build(deps): bump next from 16.3.6 to 16.3.8\n")
    assert errors
    assert any("Unknown commit type" in error for error in errors)
    assert any("chore(<scope>)" in error for error in errors)


def test_empty_message_is_rejected() -> None:
    assert checker.check_message("") == ["Empty commit message"]
    assert checker.check_message("\n\n") == ["Empty subject line"]


# ── Input resolution (repository-level cases live in the sibling module) ─


def test_check_message_still_rejects_empty_message() -> None:
    """The pure validator keeps its behaviour (guard against a weakened fix)."""
    assert checker.check_message("") == ["Empty commit message"]


def test_read_message_prefers_explicit_argv_path(tmp_path: Path) -> None:
    """Git's own commit-msg argument is the first resolution source."""
    explicit = tmp_path / "COMMIT_EDITMSG"
    explicit.write_text("feat(core): explicit path\n", encoding="utf-8")

    message = checker.read_message(
        [str(_SCRIPT), str(explicit)], stdin=io.StringIO("chore: stdin\n")
    )

    assert message == "feat(core): explicit path"
