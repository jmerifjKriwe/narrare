"""Release-tag comparison, nothing more.

A release is ``vMAJOR.MINOR.PATCH`` and its leading ``v`` is optional. Anything
else — a prerelease, a nightly, a truncated tag — is not a release this app
announces, so it is not newer (design §"version.py-adjacent comparison").
"""

import re

_RELEASE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(tag: str) -> tuple[int, int, int] | None:
    match = _RELEASE.match(tag.strip())
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def is_newer(candidate: str, current: str) -> bool:
    parsed = parse_version(candidate)
    base = parse_version(current)
    if parsed is None or base is None:
        return False
    return parsed > base
