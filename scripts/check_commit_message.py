#!/usr/bin/env python3
"""
Conventional Commits message checker.
Reads the commit message from an explicit path, git's COMMIT_EDITMSG, or stdin.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO

_GIT: Final[Path | str] = shutil.which("git") or "git"

TYPES = {
    "feat",
    "fix",
    "docs",
    "chore",
    "test",
    "refactor",
    "perf",
    "ci",
    "style",
    "revert",
}

# Pattern: type(scope)!: description
# or:      type!: description
# or:      type: description
PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(\((?P<scope>[a-z0-9/_-]+)\))?(?P<breaking>!)?"
    r": (?P<desc>.{1,100})$",
    re.MULTILINE,
)


def check_message(message: str) -> list[str]:
    """Return list of errors, empty if valid."""
    # Strip comments and whitespace
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    if not lines:
        return ["Empty commit message"]

    subject = lines[0].strip()

    if not subject:
        return ["Empty subject line"]

    # Allow merge commits
    if subject.startswith("Merge "):
        return []

    # Allow revert commits
    if subject.startswith("Revert "):
        return []

    match = PATTERN.match(subject)
    if not match:
        return [
            "Commit message does not follow Conventional Commits format.",
            f"  Got:      '{subject}'",
            "  Expected: '<type>(<scope>): <description>'",
            "  Example:  'feat(writing): add chapter reorder'",
            f"  Types:    {', '.join(sorted(TYPES))}",
        ]

    commit_type = match.group("type")
    if commit_type not in TYPES:
        return [
            f"Unknown commit type '{commit_type}'.",
            f"  Allowed types: {', '.join(sorted(TYPES))}",
        ]

    desc = match.group("desc")
    if desc[0].isupper():
        return [
            f"Description should start with lowercase: '{desc}'",
            f"  Got:      '{subject}'",
            f"  Expected: '{subject[0 : subject.index(': ') + 2]}{desc[0].lower()}{desc[1:]}'",
        ]

    return []


def read_commit_message(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
) -> str:
    """Return the commit message, resolved in this order:

    1. An explicit path in ``argv[0]`` (git's own ``commit-msg`` protocol).
    2. The message piped on ``stdin``, when stdin is not a TTY and yields a
       non-empty string. A TTY is never read (``git commit`` from a terminal
       hands the hook a terminal stdin; reading it would block). An empty
       non-TTY stdin (pre-commit, non-interactive ``git commit``) falls through.
    3. ``git rev-parse --git-path COMMIT_EDITMSG`` — correct in a normal
       checkout *and* in a linked worktree, where ``.git`` is a file.
    4. Otherwise the empty string (rejected by ``check_message``).

    A failing git call is reported on stderr (RULE-11: never swallowed).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    stream = sys.stdin if stdin is None else stdin

    if args:
        explicit = Path(args[0])
        if explicit.is_file():
            return explicit.read_text(encoding="utf-8")

    if not stream.isatty():
        piped = stream.read()
        if piped:
            return piped

    try:
        result = subprocess.run(  # noqa: S603  # nosec  # controlled git invocation, fixed argv
            [_GIT, "rev-parse", "--git-path", "COMMIT_EDITMSG"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"⚠️  Could not resolve COMMIT_EDITMSG via git: {exc}", file=sys.stderr)
        return ""

    path = Path(result.stdout.strip())
    if path.is_file():
        return path.read_text(encoding="utf-8")

    return ""


def main() -> int:
    message = read_commit_message()

    errors = check_message(message)

    if errors:
        print("\n❌ Commit message rejected:\n")
        for error in errors:
            print(f"  {error}")
        print()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
