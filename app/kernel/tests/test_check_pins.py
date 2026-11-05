"""The pin check reads every pin from the tree, and its comparisons bite."""

import re
from pathlib import Path

import pytest

from scripts import check_pins

ROOT = Path(__file__).resolve().parents[3]


def _pin(name: str, files: tuple[str, ...], pattern: str, count: int) -> check_pins.Pin:
    return check_pins.Pin(
        name=name,
        files=files,
        pattern=pattern,
        count=count,
        upstream=("github", f"owner/{name}"),
    )


def test_reads_every_pin_from_the_tree() -> None:
    states = {state.pin.name: state for state in check_pins.read_pins(ROOT)}

    assert set(states) == {
        "actionlint",
        "actionlint-digest",
        "zizmor",
        "pip-audit",
        "codecov-cli",
        "pgvector",
    }
    assert re.fullmatch(r"\d+\.\d+\.\d+", states["actionlint"].current)
    assert states["actionlint-digest"].current.startswith("sha256:")
    assert re.fullmatch(r"\d+\.\d+\.\d+", states["zizmor"].current)
    assert re.fullmatch(r"\d+\.\d+\.\d+", states["pip-audit"].current)
    assert re.fullmatch(r"v\d+\.\d+\.\d+", states["codecov-cli"].current)
    # Four blocks across three files, one digest: read_pins raises otherwise.
    assert states["pgvector"].current.startswith("sha256:")


def test_missing_pin_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "only.yml").write_text("nothing to see\n", encoding="utf-8")
    pin = _pin("missing", ("only.yml",), r"pin=(\d+)", 1)

    with pytest.raises(check_pins.PinError, match=r"only\.yml"):
        check_pins.read_pins(tmp_path, pins=(pin,))


def test_disagreeing_copies_are_an_error(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text("image: pin@sha256:aaa\n", encoding="utf-8")
    (tmp_path / "b.yml").write_text("image: pin@sha256:bbb\n", encoding="utf-8")
    pin = _pin("shared", ("a.yml", "b.yml"), r"pin@(sha256:\w+)", 2)

    with pytest.raises(check_pins.PinError, match="disagreeing"):
        check_pins.read_pins(tmp_path, pins=(pin,))


def test_a_lost_site_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text("image: pin@sha256:aaa\n", encoding="utf-8")
    (tmp_path / "b.yml").write_text("image: pin@sha256:aaa\n", encoding="utf-8")
    pin = _pin("shared", ("a.yml", "b.yml"), r"pin@(sha256:\w+)", 3)

    with pytest.raises(check_pins.PinError, match="expected 3"):
        check_pins.read_pins(tmp_path, pins=(pin,))


@pytest.mark.parametrize(
    ("current", "upstream", "is_behind"),
    [
        ("1.30.1", "v1.32.0", True),
        ("v11.3.2", "11.3.2", False),
        ("1.7.12", "v1.7.12", False),
        ("2.0.0", "1.9.9", False),
    ],
)
def test_compare_ignores_the_v_prefix(current: str, upstream: str, is_behind: bool) -> None:
    assert check_pins.compare(current, upstream) is is_behind


def test_a_changed_digest_is_behind() -> None:
    assert check_pins.compare("sha256:aaa", "sha256:bbb")
    assert not check_pins.compare("sha256:aaa", "sha256:aaa")


def test_report_names_only_the_behind_pins() -> None:
    stale = _pin("stale", ("a.yml",), r"x", 1)
    fresh = _pin("fresh", ("b.yml",), r"x", 1)
    states = [check_pins.PinState(stale, "1.0.0"), check_pins.PinState(fresh, "2.0.0")]
    upstreams = {"stale": "1.1.0", "fresh": "2.0.0"}

    text = check_pins.report(states, upstreams)

    assert text.count("**behind**") == 1
    assert text.count("| current |") == 1
    assert check_pins.behind(states, upstreams) == ["stale"]
