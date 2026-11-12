"""Check the CI pins Dependabot cannot follow.

Dependabot scans workflow files for `uses:` references and the two lockfiles.
It cannot see a Docker image digest, an action's `version:` input, or a tool
version inside a `run:` line. Those values are read from the files that carry
them — never copied here — and compared with their upstream releases by the
monthly `Tool pins` workflow, which opens one issue when any is behind.

A pin this module cannot read is an error (`PinError`), never a pass: a check
that silently finds nothing is the defect it exists to prevent.

Action pins (`owner/repo@<sha>`) are Dependabot's territory, but a SHA that does
not resolve upstream (a typo, a never-existing commit) is invisible to every
gate that only checks syntax or pinning. `check_action_pins` resolves each one
against the GitHub API and raises `PinError` on the first miss.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

DOCKER_HUB = "https://registry.hub.docker.com/v2/repositories"


class PinError(Exception):
    """A pin that cannot be read or an upstream that cannot be asked."""


@dataclass(frozen=True)
class Pin:
    """One value in the tree and where its upstream lives.

    `files` is (path, expected matches in that file). Every file is read on
    its own: a lost site in one file is an error even when another file gained
    a copy, and every match must agree. `upstream` is ("github", "owner/repo")
    or ("docker", "image", "tag"), where a tag starting with "@" names another
    pin whose current value is the tag.

    The patterns anchor on the active YAML key (`image:`, `run:`, `version:`),
    never on raw text: a digest left in a comment must not satisfy a pin whose
    live reference went back to a mutable tag.
    """

    name: str
    files: tuple[tuple[str, int], ...]
    pattern: str
    upstream: tuple[str, ...]


@dataclass(frozen=True)
class PinState:
    """What the tree says, before any upstream is asked."""

    pin: Pin
    current: str


PINS: tuple[Pin, ...] = (
    Pin(
        name="actionlint",
        files=((".github/workflows/ci.yml", 1),),
        pattern=r"^[ \t]+run:.*# rhysd/actionlint:(\d+\.\d+\.\d+)$",
        upstream=("github", "rhysd/actionlint"),
    ),
    Pin(
        name="actionlint-digest",
        files=((".github/workflows/ci.yml", 1),),
        pattern=r"^[ \t]+run:.*rhysd/actionlint@(sha256:[0-9a-f]{64})",
        upstream=("docker", "rhysd/actionlint", "@actionlint"),
    ),
    Pin(
        name="zizmor",
        files=((".github/workflows/ci.yml", 1),),
        pattern=r"^[ \t]+version:[ \t]+(\d+\.\d+\.\d+)[ \t]*$",
        upstream=("github", "zizmorcore/zizmor"),
    ),
    Pin(
        name="pip-audit",
        files=((".github/workflows/nightly.yml", 1),),
        pattern=r"^[ \t]+run:[ \t]+uvx pip-audit==(\d+\.\d+\.\d+)",
        upstream=("github", "pypa/pip-audit"),
    ),
    Pin(
        name="codecov-cli",
        files=((".github/workflows/_test.yml", 2),),
        pattern=r"^[ \t]+version:[ \t]+(v\d+\.\d+\.\d+)[ \t]*$",
        upstream=("github", "codecov/codecov-cli"),
    ),
    Pin(
        name="pgvector",
        files=(
            (".github/workflows/_test.yml", 1),
            (".github/workflows/_e2e.yml", 1),
            ("docker-compose.dev.yml", 2),
        ),
        pattern=r"^[ \t]+image:[ \t]*pgvector/pgvector@(sha256:[0-9a-f]{64})",
        upstream=("docker", "pgvector/pgvector", "pg17"),
    ),
)


def read_pins(root: Path, pins: Sequence[Pin] = PINS) -> list[PinState]:
    """Read every pin from the tree; a missing file, lost site or disagreement raises."""
    states: list[PinState] = []
    for pin in pins:
        values: list[str] = []
        for name, expected in pin.files:
            try:
                text = (root / name).read_text(encoding="utf-8")
            except OSError as error:
                raise PinError(f"{pin.name}: cannot read {name}: {error}") from error
            found = re.findall(pin.pattern, text, flags=re.MULTILINE)
            if len(found) != expected:
                raise PinError(
                    f"{pin.name}: expected {expected} match(es) in {name}, found {len(found)}"
                )
            values.extend(found)
        distinct = sorted(set(values))
        if len(distinct) != 1:
            raise PinError(
                f"{pin.name}: disagreeing values in {', '.join(name for name, _ in pin.files)}: "
                f"{distinct}"
            )
        states.append(PinState(pin=pin, current=distinct[0]))
    return states


def latest(pin: Pin, current: Mapping[str, str]) -> str:
    """Ask the pin's upstream for the value the tree should carry."""
    kind = pin.upstream[0]
    if kind == "github":
        return _github_tag(pin.upstream[1])
    if kind == "docker":
        tag = pin.upstream[2]
        if tag.startswith("@"):
            tag = current[tag[1:]]
        return _docker_digest(pin.upstream[1], tag)
    raise PinError(f"{pin.name}: unknown upstream {pin.upstream!r}")


def _github_tag(repo: str) -> str:
    executable = shutil.which("gh")
    if executable is None:
        raise PinError("gh is not on PATH")
    completed = subprocess.run(  # noqa: S603  # nosec  # fixed argv, no shell
        [executable, "api", f"repos/{repo}/releases/latest", "--jq", ".tag_name"],
        check=False,
        capture_output=True,
        text=True,
    )
    tag = completed.stdout.strip()
    if completed.returncode != 0 or not tag:
        reason = completed.stderr.strip() or "no tag in the response"
        raise PinError(f"gh api {repo} failed: {reason}")
    return tag.removeprefix("v")


def _docker_digest(image: str, tag: str) -> str:
    url = f"{DOCKER_HUB}/{image}/tags/{tag}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310  # nosec
            payload = json.load(response)
    except (OSError, ValueError) as error:
        raise PinError(f"{image}:{tag} lookup failed: {error}") from error
    digest = payload.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise PinError(f"{image}:{tag} answered without a digest")
    return digest


def _version(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.removeprefix("v").split("."))
    except ValueError as error:
        raise PinError(f"not a version: {value!r}") from error


def compare(current: str, upstream: str) -> bool:
    """True when the tree is behind its upstream; a digest is behind when it differs."""
    if current.startswith("sha256:") or upstream.startswith("sha256:"):
        return current != upstream
    return _version(current) < _version(upstream)


def _short(value: str) -> str:
    return f"{value[:14]}…" if value.startswith("sha256:") else value


def report(states: Sequence[PinState], upstreams: Mapping[str, str]) -> str:
    """One markdown table: what the tree says, what upstream says, what follows."""
    rows = [
        "| Pin | Current | Upstream | State | Where |",
        "| --- | --- | --- | --- | --- |",
    ]
    for state in states:
        pin = state.pin
        upstream = upstreams[pin.name]
        verdict = "**behind**" if compare(state.current, upstream) else "current"
        rows.append(
            f"| {pin.name} | {_short(state.current)} | {_short(upstream)} | {verdict} | "
            f"{', '.join(name for name, _ in pin.files)} |"
        )
    return "\n".join(rows)


def behind(states: Sequence[PinState], upstreams: Mapping[str, str]) -> list[str]:
    """The pin names the workflow should report, in table order."""
    return [state.pin.name for state in states if compare(state.current, upstreams[state.pin.name])]


_ACTION_USES_RE = re.compile(r"uses:\s*['\"]?([^\s'\"@]+)@([0-9a-f]{40})['\"]?\b")


def action_pins(root: Path) -> dict[str, set[str]]:
    """Collect every `owner/repo@<sha>` pin under `.github/`.

    Pure discovery: no network, no mutation. A tree with none is a defect
    (the monthly run must never be able to say "current" when it could not
    ask), so it raises `PinError` rather than returning an empty mapping.
    """

    files: list[Path] = []
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        files.extend(sorted(workflows.rglob("*.yml")))
        files.extend(sorted(workflows.rglob("*.yaml")))
    actions = root / ".github" / "actions"
    if actions.is_dir():
        files.extend(sorted(actions.rglob("action.yml")))
        files.extend(sorted(actions.rglob("action.yaml")))

    pins: dict[str, set[str]] = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise PinError(f"cannot read {path}: {error}") from error
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            for raw_repo, sha in _ACTION_USES_RE.findall(line):
                if raw_repo.startswith(".") or raw_repo.startswith("/"):
                    continue
                parts = raw_repo.split("/")
                if len(parts) < 2:
                    continue
                repo = f"{parts[0]}/{parts[1]}"
                pins.setdefault(repo, set()).add(sha)

    if not pins:
        raise PinError("no action pins found under .github/workflows or .github/actions")
    return pins


def check_action_pins(root: Path) -> None:
    """Resolve every `owner/repo@<sha>` pin in the workflow surface.

    A SHA that does not exist upstream (a typo, a never-existing commit) is
    invisible to actionlint and zizmor, and Dependabot cannot bump it. Asking
    GitHub directly is the only way to notice, and this check raises
    `PinError` on the first miss so the monthly run names it.
    """

    pins = action_pins(root)

    executable = shutil.which("gh")
    if executable is None:
        raise PinError("gh is not on PATH")

    for repo in sorted(pins):
        for sha in sorted(pins[repo]):
            completed = subprocess.run(  # noqa: S603  # nosec  # fixed argv, no shell
                [executable, "api", f"repos/{repo}/commits/{sha}", "--jq", ".sha"],
                check=False,
                capture_output=True,
                text=True,
            )
            resolved = completed.stdout.strip()
            if completed.returncode != 0 or resolved != sha:
                reason = completed.stderr.strip() or "commit not found"
                raise PinError(f"action pin {repo}@{sha} does not resolve upstream: {reason}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_pins.py",
        description="Compare the CI pins Dependabot cannot follow with their upstreams.",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="print behind[] and the report")
    output.add_argument("--markdown", action="store_true", help="print the report table")
    output.add_argument(
        "--tree",
        action="store_true",
        help="read every pin and stop: no network, exit 2 on a pin the tree does not carry",
    )
    parser.add_argument("--root", default=".", help="repository root to read (default: cwd)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Read, ask, print; 0 on success, 2 when a pin or an upstream cannot be read."""
    args = _build_parser().parse_args(argv)
    root = Path(args.root)
    try:
        states = read_pins(root)
        if args.tree:
            print(" ".join(state.pin.name for state in states))
            return 0
        # Action SHAs are network-checked here (not under --tree, which is
        # offline by contract); a miss raises PinError and reddens the run.
        check_action_pins(root)
        current = {state.pin.name: state.current for state in states}
        upstreams = {state.pin.name: latest(state.pin, current) for state in states}
        text = report(states, upstreams)
        if args.json:
            print(json.dumps({"behind": behind(states, upstreams), "report": text}))
        else:
            print(text)
    except PinError as error:
        print(f"check_pins: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
