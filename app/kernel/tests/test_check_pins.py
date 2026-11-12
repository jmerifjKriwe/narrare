"""The pin check reads every pin from the tree, and its comparisons bite."""

import re
from pathlib import Path

import pytest

from scripts import check_pins

ROOT = Path(__file__).resolve().parents[3]


def _pin(name: str, files: tuple[tuple[str, int], ...], pattern: str) -> check_pins.Pin:
    return check_pins.Pin(
        name=name,
        files=files,
        pattern=pattern,
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
    pin = _pin("missing", (("only.yml", 1),), r"pin=(\d+)")

    with pytest.raises(check_pins.PinError, match=r"expected 1 match\(es\) in only\.yml"):
        check_pins.read_pins(tmp_path, pins=(pin,))


def test_a_missing_file_is_a_pin_error(tmp_path: Path) -> None:
    pin = _pin("absent", (("absent.yml", 1),), r"pin=(\d+)")

    with pytest.raises(check_pins.PinError, match=r"cannot read absent\.yml"):
        check_pins.read_pins(tmp_path, pins=(pin,))


def test_disagreeing_copies_are_an_error(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text("image: pin@sha256:aaa\n", encoding="utf-8")
    (tmp_path / "b.yml").write_text("image: pin@sha256:bbb\n", encoding="utf-8")
    pin = _pin("shared", (("a.yml", 1), ("b.yml", 1)), r"^image: pin@(sha256:\w+)")

    with pytest.raises(check_pins.PinError, match="disagreeing"):
        check_pins.read_pins(tmp_path, pins=(pin,))


def test_a_lost_site_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text("image: pin@sha256:aaa\n", encoding="utf-8")
    (tmp_path / "b.yml").write_text("image: pin:pg17\n", encoding="utf-8")
    pin = _pin("shared", (("a.yml", 1), ("b.yml", 1)), r"^image: pin@(sha256:\w+)")

    with pytest.raises(check_pins.PinError, match=r"expected 1 match\(es\) in b\.yml"):
        check_pins.read_pins(tmp_path, pins=(pin,))


def test_a_duplicate_cannot_replace_a_lost_site(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text(
        "image: pin@sha256:aaa\nimage: pin@sha256:aaa\n", encoding="utf-8"
    )
    (tmp_path / "b.yml").write_text("image: pin:pg17\n", encoding="utf-8")
    pin = _pin("shared", (("a.yml", 2), ("b.yml", 1)), r"^image: pin@(sha256:\w+)")

    with pytest.raises(check_pins.PinError, match=r"expected 1 match\(es\) in b\.yml"):
        check_pins.read_pins(tmp_path, pins=(pin,))


def test_report_names_only_the_behind_pins() -> None:
    stale_pin = _pin("stale", (("x.yml", 1),), r"pin=(\d+)")
    fresh_pin = _pin("fresh", (("y.yml", 1),), r"pin=(\d+)")
    states = [
        check_pins.PinState(pin=stale_pin, current="1"),
        check_pins.PinState(pin=fresh_pin, current="2"),
    ]
    upstreams = {"stale": "2", "fresh": "2"}

    text = check_pins.report(states, upstreams)

    assert text.count("**behind**") == 1
    assert text.count("| current |") == 1
    assert check_pins.behind(states, upstreams) == ["stale"]


def test_action_pins_collects_a_workflow_pin(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "      - uses: actions/checkout@1111111111111111111111111111111111111111 # v7\n",
        encoding="utf-8",
    )

    pins = check_pins.action_pins(tmp_path)

    assert pins == {"actions/checkout": {"1111111111111111111111111111111111111111"}}


def test_action_pins_collects_a_quoted_pin(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "      - uses: 'actions/checkout@2222222222222222222222222222222222222222'\n",
        encoding="utf-8",
    )

    pins = check_pins.action_pins(tmp_path)

    assert pins == {"actions/checkout": {"2222222222222222222222222222222222222222"}}


def test_action_pins_ignores_commented_uses(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "#       - uses: actions/checkout@3333333333333333333333333333333333333333\n",
        encoding="utf-8",
    )

    with pytest.raises(check_pins.PinError, match="no action pins found"):
        check_pins.action_pins(tmp_path)


def test_action_pins_raises_on_an_empty_tree(tmp_path: Path) -> None:
    with pytest.raises(check_pins.PinError, match="no action pins found"):
        check_pins.action_pins(tmp_path)


def test_check_action_pins_raises_when_gh_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "      - uses: actions/checkout@4444444444444444444444444444444444444444\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_pins.shutil, "which", lambda _name: None)  # type: ignore[arg-type]

    with pytest.raises(check_pins.PinError, match="gh is not on PATH"):
        check_pins.check_action_pins(tmp_path)


def test_check_action_pins_raises_on_an_unresolvable_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "      - uses: actions/checkout@5555555555555555555555555555555555555555\n",
        encoding="utf-8",
    )

    class _Result:
        returncode = 1
        stdout = ""
        stderr = "No commit found for SHA"

    monkeypatch.setattr(check_pins.shutil, "which", lambda _name: "/usr/bin/gh")  # type: ignore[arg-type]
    monkeypatch.setattr(check_pins.subprocess, "run", lambda *a, **k: _Result())  # type: ignore[arg-type]

    with pytest.raises(check_pins.PinError, match="does not resolve upstream"):
        check_pins.check_action_pins(tmp_path)


def test_check_action_pins_accepts_a_resolving_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sha = "6666666666666666666666666666666666666666"
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        f"      - uses: actions/checkout@{sha}\n", encoding="utf-8"
    )

    class _Result:
        returncode = 0
        stdout = sha + "\n"
        stderr = ""

    monkeypatch.setattr(check_pins.shutil, "which", lambda _name: "/usr/bin/gh")  # type: ignore[arg-type]
    monkeypatch.setattr(check_pins.subprocess, "run", lambda *a, **k: _Result())  # type: ignore[arg-type]

    assert check_pins.check_action_pins(tmp_path) is None


def test_a_commented_digest_does_not_satisfy_a_pin(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text(
        "    image: pgvector/pgvector:pg17 # was pgvector/pgvector@sha256:aaa\n",
        encoding="utf-8",
    )
    pin = _pin(
        "shared",
        (("a.yml", 1),),
        r"^[ \t]+image:[ \t]*pgvector/pgvector@(sha256:\w+)",
    )

    with pytest.raises(check_pins.PinError, match=r"expected 1 match\(es\) in a\.yml"):
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
