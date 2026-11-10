"""The commit-message gate: what it accepts, what it refuses, and that a
refused message is never rewritten."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_commit_msg import USER_FACING, check, main

VISIBLE = "\n\nUser-visible: the user can see it.\n"


@pytest.mark.parametrize(
    "message",
    [
        "feat: add the thing" + VISIBLE,
        "feat(web): add the thing" + VISIBLE,
        "fix(api,web): add the thing" + VISIBLE,
        "fix(api/series): add the thing" + VISIBLE,
        "fix(core+api): add the thing" + VISIBLE,
        "feat(API): add the thing" + VISIBLE,
        "docs!: drop the old guide" + VISIBLE,
        "perf: go faster" + VISIBLE,
        "chore(deps): bump ruff\n",
        "refactor: split the thing\n",
        "test: cover the thing\n",
        "build(deps): bump ruff\n",
        "ci: tighten the gate\n",
        "style: reorder the imports\n",
        "revert: undo the thing\n",
        "Merge branch 'main' into chore/hooks\n",
        'Revert "feat: add the thing"\n',
        "fixup! feat: add the thing\n",
        "squash! feat: add the thing\n",
        "amend! feat: add the thing\n",
    ],
)
def test_parseable_messages_are_accepted(message: str) -> None:
    assert check(message) is None


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
    problem = check(f"{subject}\n")
    assert problem is not None
    assert "does not follow Conventional Commits" in problem
    assert subject.strip() in problem


@pytest.mark.parametrize(
    "subject",
    [
        "feat: add the thing",
        "fix(api): resolve the timeout",
        "perf: go faster",
        "docs: update the guide",
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        "",
        "\n",
        "\nUser-visible:\n",
        "\nUser-visible: \n",
        "\nUser-visible: none\n",
        "\nUser-visible: none — groundwork only\n",
        "\nUser-visible: none yet\n",
        "\nUser-visible: none (test infrastructure) — a reason\n",
        "\nUser-visible: none (the findings surface lands next)\n",
        "\nUser-visible: none in the product; the plan is recorded\n",
        "\nUser-visible: none user-facing yet — no component renders this\n",
        "\nUser-visible: none beyond what the flow proves\n",
        "\nUser-visible: n/a\n",
        "\nUser-visible: n/a (docs only)\n",
        "\nUser-visible: -\n",
        "\nUser-visible: - none\n",
        "\nUser-visible: (none)\n",
        "\nUser-visible: - (none)\n",
        "\nUser-visible: nothing\n",
        "\nUser-visible: nothing (see #12)\n",
        "\nUser-visible: nothing changes for existing users\n",
        "\nUser-visible: tbd\n",
        "\nUser-visible: tbd later\n",
        "\nUser-visible: none for sighted users; a screen reader now meets the answer\n",
    ],
)
def test_a_user_facing_type_needs_a_real_user_visible_line(subject: str, body: str) -> None:
    problem = check(f"{subject}\n{body}")
    assert problem is not None
    assert "User-visible" in problem


@pytest.mark.parametrize(
    "subject",
    [
        "chore(deps): bump ruff",
        "refactor: split the thing",
        "test: cover the thing",
        "build(deps): bump ruff",
        "ci: tighten the gate",
        "style: reorder the imports",
        "revert: undo the thing",
    ],
)
def test_a_type_outside_the_release_notes_needs_no_user_visible_line(
    subject: str,
) -> None:
    assert check(f"{subject}\n") is None


def test_a_commented_user_visible_line_does_not_count() -> None:
    message = "feat: add the thing\n\n# User-visible: the user can see it.\n"
    assert check(message) is not None


def test_a_user_visible_line_after_the_verbose_scissors_does_not_count() -> None:
    message = (
        "feat: add the thing\n"
        "\n"
        "# ------------------------ >8 ------------------------\n"
        "User-visible: the user can see it.\n"
    )

    assert check(message) is not None


def test_a_real_user_visible_line_among_prose_is_accepted() -> None:
    message = (
        "fix(web): keep the form\n"
        "\n"
        "The form lost its state on submit.\n"
        "\n"
        "User-visible: the form keeps what you typed.\n"
    )

    assert check(message) is None


def test_a_sentence_that_starts_with_none_is_still_real() -> None:
    message = "docs: update the guide\n\nUser-visible: None of the old commands remain.\n"

    assert check(message) is None


def test_a_bulleted_real_effect_is_accepted() -> None:
    message = "fix(web): keep the form\n\nUser-visible: - The form keeps its state.\n"

    assert check(message) is None


def test_a_crlf_message_keeps_its_user_visible_line() -> None:
    message = "feat: add the thing\r\n\r\nUser-visible: the user can see it.\r\n"

    assert check(message) is None


def test_user_facing_matches_the_visible_changelog_sections() -> None:
    config = json.loads(
        (Path(__file__).resolve().parents[3] / "release-please-config.json").read_text(
            encoding="utf-8"
        )
    )
    sections = config["packages"]["."]["changelog-sections"]
    visible = {section["type"] for section in sections if not section.get("hidden")}

    assert visible == USER_FACING


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


def test_a_user_facing_message_without_user_visible_exits_one(
    tmp_path: Path,
) -> None:
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("feat: add the thing\n", encoding="utf-8")

    assert main(["check_commit_msg.py", str(message)]) == 1


def test_a_user_facing_message_with_user_visible_exits_zero(
    tmp_path: Path,
) -> None:
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text(
        "feat: add the thing\n\nUser-visible: the thing is there.\n",
        encoding="utf-8",
    )

    assert main(["check_commit_msg.py", str(message)]) == 0


def test_a_missing_filename_is_a_usage_error() -> None:
    assert main(["check_commit_msg.py"]) == 2


def test_an_unreadable_message_is_an_error(tmp_path: Path) -> None:
    message = tmp_path / "absent"
    assert main(["check_commit_msg.py", str(message)]) == 2

    undecodable = tmp_path / "COMMIT_EDITMSG"
    undecodable.write_bytes(b"\xff\xfe\n")
    assert main(["check_commit_msg.py", str(undecodable)]) == 2
