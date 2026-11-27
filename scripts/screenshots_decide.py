"""Decide whether a Screenshots push should regenerate the README's images.

The workflow asks one question on every push to ``main``: did a UI-relevant
path change, or did a commit ask for a run explicitly? This module answers it
from git history so the decision is testable without GitHub.

Two details are deliberate. Footer scanning uses ``git log --no-merges``:
GitHub writes an editable pull request title into the merge commit's body, and
a title is not a footer the pushed commits' author wrote, so it must not force
or suppress a capture. Changed paths are copied out whole and matched in
process: a ``grep -q`` pipeline closes its producer early, and under
``pipefail`` the producer's SIGPIPE would turn a real UI change into a "no UI
path" answer once the path list outgrows the pipe buffer (#982).

The CLI prints ``run=true|false`` and ``reason=...``; the workflow appends both
lines to ``$GITHUB_OUTPUT``. Manual dispatch and the schedule always run, a
first push treats everything as changed, and the explicit commit footers keep
their precedence: ``Screenshots: regenerate`` wins over everything, ``skip``
suppresses only when no UI path changed.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess  # nosec B404 - fixed argv git queries, no shell
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# A path whose change can alter a captured frame. The list is the contract the
# workflow documents in CONTRIBUTING.md.
UI_PATH = re.compile(
    r"^(?:web/|app/capabilities/[^/]+/web/|i18n/"
    r"|scripts/screenshots\.py$|scripts/screenshot_manifest\.py$)"
)

REGENERATE_FOOTER = re.compile(
    r"^Screenshots:[ \t]*regenerate[ \t\r]*$",
    re.IGNORECASE | re.MULTILINE,
)
SKIP_FOOTER = re.compile(
    r"^Screenshots:[ \t]*skip[ \t\r]*$",
    re.IGNORECASE | re.MULTILINE,
)

SKIP_REASON = "no UI path changed and no regenerate override; skipping"


def _git(root: Path, *args: str) -> str:
    """Run one git query in ``root`` and return its complete output."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git is required to decide whether to regenerate screenshots")
    completed = subprocess.run(  # noqa: S603  # nosec  # fixed argv, no shell
        [executable, *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip()
        raise RuntimeError(f"git {' '.join(args)} failed ({completed.returncode}): {detail}")
    return completed.stdout


def decide(event: str, before: str, sha: str, root: Path) -> tuple[bool, str]:
    """Whether this event regenerates the images, and the reason in one line."""
    if event != "push":
        return True, f"{event}: always regenerate"
    if not before or not before.strip("0"):
        return True, "first push: regenerate"

    # A merge commit's body carries GitHub's editable PR title; only commits
    # an author wrote may override the path decision.
    commits = _git(root, "log", "--no-merges", "--format=%B", f"{before}..{sha}")
    if REGENERATE_FOOTER.search(commits):
        return True, "override: regenerate requested"

    # NUL-separated so a filename containing a newline stays one path, and
    # read to completion instead of through an early-closing reader.
    changed = _git(root, "diff", "--name-only", "-z", before, sha)
    if any(UI_PATH.match(path) for path in changed.split("\0") if path):
        return True, "UI path changed: regenerate"

    if SKIP_FOOTER.search(commits):
        return False, "override: skip requested and no UI path changed"
    return False, SKIP_REASON


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decide whether the Screenshots workflow should regenerate."
    )
    parser.add_argument("--event", required=True, help="the GitHub event name")
    parser.add_argument("--before", required=True, help="the push's previous commit")
    parser.add_argument("--sha", required=True, help="the pushed commit")
    parser.add_argument("--root", type=Path, default=Path(), help="the repository root")
    args = parser.parse_args(argv)
    run, reason = decide(args.event, args.before, args.sha, args.root)
    print(f"run={'true' if run else 'false'}")
    print(f"reason={reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
