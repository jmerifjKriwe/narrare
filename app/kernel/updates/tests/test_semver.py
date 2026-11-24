import pytest

from app.kernel.updates.semver import is_newer, parse_version


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.6.0", (0, 6, 0)),
        ("0.6.0", (0, 6, 0)),
        ("v1.10.3", (1, 10, 3)),
    ],
)
def test_parse_version_accepts_release_tags(tag: str, expected: tuple[int, int, int]) -> None:
    assert parse_version(tag) == expected


@pytest.mark.parametrize("tag", ["v1.0.0-rc.1", "nightly", "", "v1.0"])
def test_parse_version_refuses_non_releases(tag: str) -> None:
    assert parse_version(tag) is None


@pytest.mark.parametrize(
    ("candidate", "current", "expected"),
    [
        ("v0.6.0", "0.5.0", True),
        ("v1.0.0", "0.9.9", True),
        ("v0.5.0", "0.5.0", False),
        ("v0.4.9", "0.5.0", False),
        ("v0.6.0-rc.1", "0.5.0", False),
    ],
)
def test_is_newer(candidate: str, current: str, expected: bool) -> None:
    assert is_newer(candidate, current) is expected
