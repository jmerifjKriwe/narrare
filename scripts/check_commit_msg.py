#!/usr/bin/env python3
"""Repository commit-message gate: the subject's Conventional Commit type.

release-please reads the type from every commit on ``main`` and builds the
changelog and the version bump from it. A subject it cannot parse (``Update
the hooks``) disappears from both without an error anywhere, so the type is
checked here rather than noticed by its absence in a release.

Only the mechanical part is checked. A ``feat`` or ``fix`` owes a real
``User-visible:`` line, but "real" is a judgement CONTRIBUTING assigns to
review: a hook can tell an empty line from a full one, never an honest
sentence from a placeholder.

The hook never rewrites the message. It refuses an unparseable subject and
says what it expected, so a message written by hand stays as its author wrote
it.

Exit codes: 0 accepted, 1 refused, 2 usage or unreadable file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# The types release-please maps, plus the Conventional Commit types it leaves
# out of the changelog (build, style) and the one git writes itself (revert).
# The scope is what the parser takes between the parentheses — any run without
# a space or a parenthesis — not a vocabulary this hook invents.
CONVENTIONAL = re.compile(
    r"^(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\([^()\s]+\))?!?: \S"
)

# Messages git or its rebase tools write, which no author types by hand.
EXEMPT = ("Merge ", 'Revert "', "fixup! ", "squash! ", "amend! ")

# Everything after this line is the diff of `git commit --verbose`.
SCISSORS = "# ------------------------ >8 ------------------------"


def content_lines(message: str) -> list[str]:
    """The message without git's comment lines and the verbose diff."""
    lines: list[str] = []
    for line in message.splitlines():
        if line.startswith(SCISSORS):
            break
        if line.startswith("#"):
            continue
        lines.append(line)
    return lines


def check(message: str) -> str | None:
    """Return the offending subject, or ``None`` when the message is accepted."""
    subject = next(
        (line.strip() for line in content_lines(message) if line.strip()),
        "",
    )
    if not subject:
        # An empty message is git's refusal to make, not this hook's.
        return None
    if subject.startswith(EXEMPT):
        return None
    if CONVENTIONAL.match(subject):
        return None
    return subject


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_commit_msg.py <commit-message-file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        message = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"cannot read {path}: {error}", file=sys.stderr)
        return 2

    offending = check(message)
    if offending is None:
        return 0

    print(
        "The commit subject does not follow Conventional Commits:\n"
        f"  {offending}\n"
        "Expected: type(scope): effect, with type one of feat, fix, docs, style,\n"
        "refactor, perf, test, build, ci, chore, revert, and a scope without\n"
        "spaces. release-please reads the type; a subject it cannot parse is\n"
        "lost from the changelog.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
