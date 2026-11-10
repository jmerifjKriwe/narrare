#!/usr/bin/env python3
"""Repository commit-message gate: the subject's Conventional Commit type and
its user-visible claim.

release-please reads the type from every commit on ``main`` and builds the
changelog and the version bump from it. A subject it cannot parse (``Update
the hooks``) disappears from both without an error anywhere, so the type is
checked here rather than noticed by its absence in a release.

The types that reach the changelog (``feat``, ``fix``, ``perf``, ``docs``)
also owe a real ``User-visible:`` line: the release notes are the user's
record, and a ``feat`` whose body says ``none`` is development work that
belongs under a hidden type. "Real" is still a judgement review owns — this
hook refuses an empty or placeholder value, never an honest sentence.

The hook never rewrites the message. It refuses an unusable message and says
what it expected, so a message written by hand stays as its author wrote it.

Exit codes: 0 accepted, 1 refused, 2 usage or unreadable file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# The conventional types release-please can see, plus the ones this
# repository's release-please-config.json leaves out of the changelog (build,
# style, revert and the hidden sections). The scope is what the parser takes
# between the parentheses — any run without a space or a parenthesis — not a
# vocabulary this hook invents.
CONVENTIONAL = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\([^()\s]+\))?!?: \S"
)

# The types that reach the changelog, and so owe a user-visible effect.
USER_FACING = frozenset({"feat", "fix", "perf", "docs"})

USER_VISIBLE = re.compile(r"^User-visible:\s*(.*)$", re.IGNORECASE)

# A value asks for no user-visible effect when it starts with one of these
# words, unless it continues as the sentence "None of the old commands remain".
PLACEHOLDER_WORD = re.compile(r"^(none|nothing|n/?a|na|tbd)\b", re.IGNORECASE)

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


def is_placeholder(value: str) -> bool:
    """Whether a ``User-visible:`` value names no user-visible effect.

    A placeholder is one of the words alone or followed by any qualifier, a
    bare or placeholder bullet, or a parenthesised placeholder. The one
    exception is the sentence form ``None of the old commands remain``: it
    starts with a placeholder word but says what a user can now do.
    """
    text = value.strip()
    if not text:
        return True
    if text.startswith(("-", "—")):
        remainder = text.lstrip("-— ").strip()
        return not remainder or is_placeholder(remainder)
    if text.startswith(("(", "[")):
        return is_placeholder(text[1:].lstrip())
    match = PLACEHOLDER_WORD.match(text)
    if match is None:
        return False
    if match.group(1).casefold() == "tbd":
        return True
    remainder = text[match.end() :]
    return not remainder.lstrip().casefold().startswith("of ")


def has_real_user_visible(lines: list[str]) -> bool:
    """Whether any line names a user-visible effect rather than a placeholder."""
    for line in lines:
        match = USER_VISIBLE.match(line.strip())
        if match is None:
            continue
        value = match.group(1).strip()
        if value and not is_placeholder(value):
            return True
    return False


def check(message: str) -> str | None:
    """Return the refusal, or ``None`` when the message is accepted."""
    lines = content_lines(message)
    subject = next((line.strip() for line in lines if line.strip()), "")
    if not subject:
        # An empty message is git's refusal to make, not this hook's.
        return None
    if subject.startswith(EXEMPT):
        return None
    match = CONVENTIONAL.match(subject)
    if match is None:
        return (
            "The commit subject does not follow Conventional Commits:\n"
            f"  {subject}\n"
            "Expected: type(scope): effect, with type one of feat, fix, docs, style,\n"
            "refactor, perf, test, build, ci, chore, revert, and a scope without\n"
            "spaces. release-please reads the type; a subject it cannot parse is\n"
            "lost from the changelog."
        )
    kind = match.group(1)
    if kind in USER_FACING and not has_real_user_visible(lines):
        return (
            f"`{kind}` reaches the release notes, so it needs a real "
            "`User-visible:` line:\n"
            f"  {subject}\n"
            "State what a user can now do or read, or move development-only work\n"
            "to a hidden type (chore, refactor, test, ci, build, style);\n"
            "development documentation is `chore(docs)`. A placeholder (`none`,\n"
            "`n/a`, `-`, `nothing`, `tbd`) is not a user-visible effect."
        )
    return None


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

    problem = check(message)
    if problem is None:
        return 0

    print(problem, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
