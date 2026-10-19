#!/usr/bin/env python3
"""
Conventional Commits message checker.

Reads the commit message from, in order:
  1. argv[1]              — pre-commit `commit-msg` hook (git passes the message file)
  2. stdin                — CI and `just check-commit-msg` (non-tty)
  3. .git/COMMIT_EDITMSG  — interactive local runs

`feat` and `fix` claim a user-facing change: they bump the version
(`feat` → minor, `fix` → patch) and land in the user-facing CHANGELOG.
Such a commit must state that claim in its body as a `User-visible:` line.
Internal production code that no user can observe belongs under
`chore(<scope>):` instead — hidden from the changelog, no version bump.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

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

# Types that claim a user-observable change (version bump + visible changelog).
USER_VISIBLE_TYPES = {"feat", "fix"}

# Pattern: type(scope)!: description
# or:      type!: description
# or:      type: description
PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(\((?P<scope>[a-z0-9/_-]+)\))?(?P<breaking>!)?"
    r": (?P<desc>.{1,100})$",
    re.MULTILINE,
)

# The user-visible claim: a body line naming what a user can now do or observe.
# The shape check lives here; the length floor is inline in
# _check_user_visible() — it is a convention floor, not configuration.
USER_VISIBLE_RE = re.compile(r"^User-visible:[ \t]*(\S.*)$", re.MULTILINE)

PLACEHOLDERS = {"-", "n/a", "none", "tbd", "todo", "see above"}

COMMIT_EDITMSG = Path(".git/COMMIT_EDITMSG")


def read_message(argv: list[str]) -> str:
    """Return the commit message from the hook file, stdin, or the editor file.

    `#`-prefixed lines are git's comment syntax and only occur in the
    message file git hands us — never in CI-supplied text (a PR body may
    legitimately contain Markdown headings).
    """
    if len(argv) > 1:
        return _strip_comments(Path(argv[1]).read_text(encoding="utf-8"))
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return _strip_comments(COMMIT_EDITMSG.read_text(encoding="utf-8"))


def _strip_comments(raw: str) -> str:
    """Drop git's `#`-prefixed comment lines from a message file."""
    return "\n".join(line for line in raw.splitlines() if not line.startswith("#"))


def check_message(message: str) -> list[str]:
    """Return list of errors, empty if valid."""
    lines = message.splitlines()
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
            "  Internal production code?  use 'chore(<scope>): …'.",
        ]

    errors: list[str] = []

    desc = match.group("desc")
    if desc[0].isupper():
        errors.append(f"Description should start with lowercase: '{desc}'")
        errors.append(f"  Got:      '{subject}'")
        errors.append(
            f"  Expected: '{subject[0 : subject.index(': ') + 2]}{desc[0].lower()}{desc[1:]}'"
        )

    if commit_type in USER_VISIBLE_TYPES:
        errors.extend(_check_user_visible(commit_type, "\n".join(lines[1:])))

    return errors


def _check_user_visible(commit_type: str, body: str) -> list[str]:
    """Require a `User-visible:` claim for the user-facing commit types."""
    match = USER_VISIBLE_RE.search(body)
    if not match:
        return [
            f"'{commit_type}' claims a user-facing change — state it for the user.",
            "  Body line:  User-visible: <what a user can now do or observe>",
            "  Internal?   use 'chore(<scope>): …' instead (hidden, no version bump)",
        ]

    text = match.group(1).strip()
    if text.lower().strip(" .!") in PLACEHOLDERS:
        return [
            f"'User-visible:' value is a placeholder: '{text}'.",
            "  Name the user-facing effect, or use 'chore(<scope>): …'.",
        ]

    # A shorter value is a placeholder ("n/a", "later") in disguise rather than
    # a statement of what a user can now do.
    if len(text) < 20:
        return [
            f"'User-visible:' value is too short ({len(text)} chars, minimum 20): '{text}'.",
            "  Name the user-facing effect, or use 'chore(<scope>): …'.",
        ]

    return []


def main(argv: list[str] | None = None) -> int:
    message = read_message(sys.argv if argv is None else argv)

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
