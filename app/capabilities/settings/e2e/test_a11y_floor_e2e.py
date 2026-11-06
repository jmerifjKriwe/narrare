"""The a11y floor names the element it failed on, not only the selector.

axe's ``node.target`` is a CSS path: a class or a tag selector can be
ambiguous, and #451's ``.px-1\\.5`` line pointed at a node the rule should
never have matched at all. ``node.html`` is what turns a rule id into an
element, so the floor carries it — bounded, because a section's outerHTML is
tens of kilobytes and the failure text has to stay readable.

These tests drive the shipped ``assert_accessible`` path — file check, script
injection, evaluate, failure formatting — and stub only the axe build itself,
so the report is synthetic while everything around it is the real code.
"""

import json
from typing import TYPE_CHECKING

import pytest

from app.kernel.testing import a11y
from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Page
    from pytest import MonkeyPatch

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def _node(markup: str, target: str = "button") -> dict[str, object]:
    return {
        "target": [target],
        "failureSummary": (
            "Fix any of the following:\n"
            "  Text inside the element is not included in the accessible name"
        ),
        "html": markup,
    }


def _violation(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "id": "label-content-name-mismatch",
            "impact": "serious",
            "help": "Elements must have their visible text as part of their accessible name",
            "helpUrl": (
                "https://dequeuniversity.com/rules/axe/4.14/"
                "label-content-name-mismatch?application=axeAPI"
            ),
            "nodes": nodes,
        }
    ]


def _inject_stub(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    violations: list[dict[str, object]],
) -> None:
    """Point the floor at a stub axe build that answers with ``violations``."""
    stub = tmp_path / "axe-stub.js"
    stub.write_text(
        f"window.axe = {{ run: () => Promise.resolve({json.dumps({'violations': violations})}) }};",
        encoding="utf-8",
    )
    monkeypatch.setattr(a11y, "AXE_PATH", stub)


def _failed_verdict(page: Page) -> str:
    page.set_content("<main><p>Text</p></main>")
    with pytest.raises(pytest.fail.Exception) as failure:
        assert_accessible(page)
    return str(failure.value)


def test_the_failure_names_the_element_markup(
    page: Page, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    markup = '<button aria-label="Einstellungen">Sprache</button>'
    _inject_stub(tmp_path, monkeypatch, _violation([_node(markup)]))

    message = _failed_verdict(page)

    assert f"html: {markup}" in message


def test_the_markup_is_one_bounded_line(
    page: Page, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    markup = '<section\n   class="long">' + "y" * 5000 + "</section>"
    _inject_stub(tmp_path, monkeypatch, _violation([_node(markup)]))

    message = _failed_verdict(page)

    lines = [line.strip() for line in message.splitlines() if line.strip().startswith("html:")]
    assert len(lines) == 1, message
    line = lines[0]
    # Whitespace collapses, the tail is cut, and the marker says so: one line
    # that survives a terminal and a paste into an issue.
    assert line.startswith('html: <section class="long">'), line
    assert line.endswith("…"), line
    assert len(line) <= len("html: ") + 201, line


def test_a_violation_says_how_many_nodes_it_did_not_print(
    page: Page, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    nodes = [
        _node(f"<button>{index}</button>", f"button:nth-of-type({index})") for index in range(1, 8)
    ]
    _inject_stub(tmp_path, monkeypatch, _violation(nodes))

    message = _failed_verdict(page)

    assert "… 2 more nodes" in message
    assert "html: <button>5</button>" in message
    assert "html: <button>6</button>" not in message


def test_a_passing_report_does_not_fail(
    page: Page, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    _inject_stub(tmp_path, monkeypatch, [])

    page.set_content("<main><p>Text</p></main>")
    assert_accessible(page)
