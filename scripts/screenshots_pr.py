"""Find an open screenshot update PR so a repeated run defers to it.

Capture output is deterministic, so an unmerged regeneration PR holds the same
asset and index diff a later scheduled or manual run would produce again.
Opening a second PR adds review work and two branches with identical content,
never a different result. This module asks GitHub for the open PRs the
workflow itself opens (``chore/screenshots-*`` against ``main``) and returns
the oldest one.

Only a same-repository PR counts: a fork may use the same branch name without
being the workflow's branch. ``gh`` is invoked with a fixed argv and no shell,
and the token is passed through its environment. The CLI prints
``pending=<number>`` or ``pending=none`` for the workflow; finding a PR is a
successful outcome, not a failure.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 - fixed argv gh query, no shell
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

SCREENSHOT_BRANCH_PREFIX = "chore/screenshots-"
BASE_BRANCH = "main"
JSON_FIELDS = "number,headRefName,isCrossRepository"
NONE = "pending=none"


def _gh_binary() -> str:
    """Resolve ``gh`` to an absolute path; the workflow runner always has it."""
    resolved = shutil.which("gh")
    if resolved is None:
        raise RuntimeError("gh is required to look up pending screenshot pull requests")
    return resolved


def pending_screenshot_pr(repository: str, token: str) -> int | None:
    """The oldest open same-repository ``chore/screenshots-*`` PR against main."""
    completed = subprocess.run(  # noqa: S603  # nosec  # fixed argv, no shell
        [
            _gh_binary(),
            "pr",
            "list",
            "--repo",
            repository,
            "--base",
            BASE_BRANCH,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            JSON_FIELDS,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "GH_TOKEN": token},
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip()
        raise RuntimeError(f"gh pr list failed ({completed.returncode}): {detail}")
    pull_requests: list[dict[str, object]] = json.loads(completed.stdout)
    numbers = [
        int(str(pull_request["number"]))
        for pull_request in pull_requests
        if str(pull_request.get("headRefName", "")).startswith(SCREENSHOT_BRANCH_PREFIX)
        and not pull_request.get("isCrossRepository", False)
    ]
    return min(numbers) if numbers else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report an open screenshot update pull request, if one exists."
    )
    parser.add_argument("--repository", required=True, help="owner/name of the repository")
    parser.add_argument(
        "--token",
        default="",
        help="token for the GitHub query; defaults to $GH_TOKEN, which keeps it out of argv",
    )
    args = parser.parse_args(argv)
    token = args.token or os.environ.get("GH_TOKEN", "")
    if not token:
        parser.error("--token or GH_TOKEN is required")
    number = pending_screenshot_pr(args.repository, token)
    print(NONE if number is None else f"pending={number}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
