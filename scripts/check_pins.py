"""Check the CI pins Dependabot cannot follow.

Dependabot scans workflow files for `uses:` references and the two lockfiles.
It cannot see a Docker image digest, an action's `version:` input, or a tool
version inside a `run:` line. Those values are read from the files that carry
them — never copied here — and compared with their upstream releases by the
monthly `Tool pins` workflow, which opens one issue when any is behind.

A pin this module cannot read is an error (`PinError`), never a pass: a check
that silently finds nothing is the defect it exists to prevent.
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

    `count` is the exact number of matches expected; None means every match
    must agree (a value written in several service blocks). `upstream` is
    ("github", "owner/repo") or ("docker", "image", "tag"), where a tag
    starting with "@" names another pin whose current value is the tag.
    """

    name: str
    files: tuple[str, ...]
    pattern: str
    count: int | None
    upstream: tuple[str, ...]


@dataclass(frozen=True)
class PinState:
    """What the tree says, before any upstream is asked."""

    pin: Pin
    current: str


PINS: tuple[Pin, ...] = (
    Pin(
        name="actionlint",
        files=(".github/workflows/ci.yml",),
        pattern=r"#\s*rhysd/actionlint:(\d+\.\d+\.\d+)",
        count=1,
        upstream=("github", "rhysd/actionlint"),
    ),
    Pin(
        name="actionlint-digest",
        files=(".github/workflows/ci.yml",),
        pattern=r"rhysd/actionlint@(sha256:[0-9a-f]{64})",
        count=1,
        upstream=("docker", "rhysd/actionlint", "@actionlint"),
    ),
    Pin(
        name="zizmor",
        files=(".github/workflows/ci.yml",),
        pattern=r"^\s+version:\s+(\d+\.\d+\.\d+)$",
        count=1,
        upstream=("github", "zizmorcore/zizmor"),
    ),
    Pin(
        name="pip-audit",
        files=(".github/workflows/nightly.yml",),
        pattern=r"uvx pip-audit==(\d+\.\d+\.\d+)",
        count=1,
        upstream=("github", "pypa/pip-audit"),
    ),
    Pin(
        name="codecov-cli",
        files=(".github/workflows/_test.yml",),
        pattern=r"^\s+version:\s+(v\d+\.\d+\.\d+)$",
        count=None,
        upstream=("github", "codecov/codecov-cli"),
    ),
    Pin(
        name="pgvector",
        files=(
            ".github/workflows/_test.yml",
            ".github/workflows/_e2e.yml",
            "docker-compose.dev.yml",
        ),
        pattern=r"pgvector/pgvector@(sha256:[0-9a-f]{64})",
        count=None,
        upstream=("docker", "pgvector/pgvector", "pg17"),
    ),
)


def read_pins(root: Path, pins: Sequence[Pin] = PINS) -> list[PinState]:
    """Read every pin from the tree; a missing or disagreeing value raises."""
    states: list[PinState] = []
    for pin in pins:
        values: list[str] = []
        for name in pin.files:
            text = (root / name).read_text(encoding="utf-8")
            found = re.findall(pin.pattern, text, flags=re.MULTILINE)
            if not found:
                raise PinError(f"{pin.name}: no match for {pin.pattern!r} in {name}")
            values.extend(found)
        if pin.count is not None and len(values) != pin.count:
            raise PinError(
                f"{pin.name}: expected {pin.count} match(es), found {len(values)} in "
                f"{', '.join(pin.files)}"
            )
        distinct = sorted(set(values))
        if len(distinct) != 1:
            raise PinError(f"{pin.name}: disagreeing values in {', '.join(pin.files)}: {distinct}")
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
            f"{', '.join(pin.files)} |"
        )
    return "\n".join(rows)


def behind(states: Sequence[PinState], upstreams: Mapping[str, str]) -> list[str]:
    """The pin names the workflow should report, in table order."""
    return [state.pin.name for state in states if compare(state.current, upstreams[state.pin.name])]


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
