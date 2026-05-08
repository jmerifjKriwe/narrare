#!/usr/bin/env python3
"""
Conventional Commits message checker.
Reads commit message from .git/COMMIT_EDITMSG or stdin.
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


def main() -> int:
    # Try to read from .git/COMMIT_EDITMSG first (pre-commit hook)
    commit_msg_file = Path(".git/COMMIT_EDITMSG")
    if commit_msg_file.exists():
        message = commit_msg_file.read_text(encoding="utf-8")
    else:
        message = sys.stdin.read()

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
