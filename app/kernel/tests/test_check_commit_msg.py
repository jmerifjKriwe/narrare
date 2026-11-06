"""The commit-message gate: what it accepts, what it refuses, and that a
refused message is never rewritten."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts.check_commit_msg import check, main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "subject",
    [
        "feat: add the thing",
        "feat(web): add the thing",
        "fix(api,web): add the thing",
        "fix(api/series): add the thing",
        "fix(core+api): add the thing",
        "feat(API): add the thing",
        "docs!: drop the old guide",
        "chore(deps): bump ruff",
        "build(deps): bump ruff",
        "style: reorder the imports",
        "revert: undo the thing",
        "Merge branch 'main' into chore/hooks",
        'Revert "feat: add the thing"',
        "fixup! feat: add the thing",
        "squash! feat: add the thing",
        "amend! feat: add the thing",
    ],
)
def test_parseable_subjects_are_accepted(subject: str) -> None:
    assert check(f"{subject}\n") is None


@pytest.mark.parametrize(
    "subject",
    [
        "Update the hooks",
        "Feat(web): capital type",
        "feet: unknown type",
        "feat: ",
        "feat(): empty scope",
        "feat(a b): spaced scope",
        "feat (web): spaced type",
        "feat(web) : spaced colon",
    ],
)
def test_unparseable_subjects_are_refused(subject: str) -> None:
    assert check(f"{subject}\n") == subject.strip()


def test_comments_and_the_verbose_scissors_are_not_the_subject() -> None:
    message = (
        "# a comment git would strip\n"
        "chore(hooks): the real subject\n"
        "\n"
        "# ------------------------ >8 ------------------------\n"
        "Update the hooks\n"
    )

    assert check(message) is None


def test_an_empty_message_is_left_to_git() -> None:
    assert check("\n# only comments\n") is None


def test_a_refused_message_is_not_rewritten(tmp_path: Path) -> None:
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("Update the hooks\n", encoding="utf-8")

    assert main(["check_commit_msg.py", str(message)]) == 1
    assert message.read_text(encoding="utf-8") == "Update the hooks\n"


def test_a_parseable_message_exits_zero(tmp_path: Path) -> None:
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("chore(hooks): tighten the gates\n", encoding="utf-8")

    assert main(["check_commit_msg.py", str(message)]) == 0


def test_a_missing_filename_is_a_usage_error() -> None:
    assert main(["check_commit_msg.py"]) == 2


def test_an_unreadable_message_is_an_error(tmp_path: Path) -> None:
    assert main(["check_commit_msg.py", str(tmp_path / "absent")]) == 2

    undecodable = tmp_path / "COMMIT_EDITMSG"
    undecodable.write_bytes(b"\xff\xfe\n")
    assert main(["check_commit_msg.py", str(undecodable)]) == 2
