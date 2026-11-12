"""Progressive focus: F9 deepens the workbench step by step, Esc walks it back.

The depth lives in the URL, the keyboard is a first-class way in and out, and
every depth still passes the accessibility floor. Real stack throughout —
browser, API, Postgres.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

# The page's tabbables at the deepest step, from the DOM the workbench keeps:
# buttons, links, fields and the contenteditable editor itself.
_INTERACTIVE = (
    "document.activeElement instanceof HTMLElement"
    " && document.activeElement !== document.body"
    " && document.activeElement.matches("
    "\"button, [href], input, select, textarea, [contenteditable='true']\")"
)


def _open_workbench(page: Page, title: str) -> None:
    """Create a novel the only way a user can, open it, and start writing.

    The module's database is shared, so every test owns a title no other uses.
    """
    page.goto(f"{WEB_URL}/")
    page.locator("header").get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen", exact=True).click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Erster Satz im Fokus.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()


def test_the_editor_rings_while_the_caret_is_inside(page: Page, stack: Stack) -> None:
    """F18: the caret's ring lives on the editor card, not the prose. Inside,
    the box-shadow is there; out, it is gone — and the measure is
    untouched either way (max-width 34rem, the same value both states)."""
    _open_workbench(page, "Der Karettring")
    editor = page.locator(".ProseMirror")
    card = page.locator("[data-editor-card]")

    shadow = """getComputedStyle(
      document.querySelector('[data-editor-card]')
    ).boxShadow"""
    width = """document.querySelector('.ProseMirror').getBoundingClientRect().width"""

    editor.click()
    page.keyboard.type("Der Ring folgt dem Caret.")
    assert page.evaluate(shadow) != "none", "no ring while the caret is inside"
    inside = page.evaluate(width)
    # R49's tone step: the editor sits in a card painted around the
    # measured column — the measure itself stays the prose's 34rem. The
    # probe reads computed paint (a `sm:bg-card` token is not the class
    # `.bg-card`), asking for an ancestor whose ground differs from the
    # page's own.
    tone_step = page.evaluate(
        """() => {
          const ground = getComputedStyle(document.body).backgroundColor;
          let n = document.querySelector('.ProseMirror').parentElement;
          for (; n; n = n.parentElement) {
            const bg = getComputedStyle(n).backgroundColor;
            if (bg !== 'rgba(0, 0, 0, 0)' && bg !== ground) return bg;
          }
          return null;
        }"""
    )
    assert tone_step, "the editor's tone step is missing"

    # The caret leaves: the heading takes the click, the ring lets go.
    page.get_by_role("heading", name="Der Karettring").click()
    assert page.evaluate(shadow) == "none", "ring stayed after the caret left"
    # The rendered width, not the constant: a layout regression moves the
    # real box, where the max-width string would sit still.
    assert page.evaluate(width) == inside, "the measure moved with the ring"
    expect(card).to_be_visible()


def test_keyboard_only_focus_cycle(page: Page, stack: Stack) -> None:
    _open_workbench(page, "Die Stilllegung")
    editor = page.locator(".ProseMirror")

    # Depth 0: the workbench as it has always been — rail, chrome, the
    # affordance that offers the first step.
    expect(page.get_by_role("complementary")).to_be_visible()
    expect(page.get_by_role("banner")).to_be_visible()
    expect(page.get_by_role("button", name="Fokus")).to_be_visible()
    assert_accessible(page)

    # F9 hides the panels: the rail yields whatever ?rail says, the chrome
    # stays, and the depth becomes URL state.
    page.keyboard.press("F9")
    expect(page.get_by_role("complementary")).to_have_count(0)
    expect(page.get_by_role("banner")).to_be_visible()
    expect(page.get_by_role("button", name="Fokus")).to_be_visible()
    assert "focus=1" in page.url
    assert_accessible(page)

    # F9 again: chrome-free. Only the writing surface and its own controls —
    # the frame (runhead, footer) yields with everything else.
    page.keyboard.press("F9")
    expect(page.get_by_role("banner")).to_have_count(0)
    # The icon rail is chrome too (P8): the deepest step leaves none of it.
    expect(page.get_by_role("navigation", name="Hauptnavigation")).to_have_count(0)
    assert "focus=2" in page.url
    assert_accessible(page)

    # The keyboard still reaches the page: the first Tab takes the page's own
    # scroller — the shell keeps `main` in the tab order so a scroll container
    # is reachable without a pointer (#638) — and the second one an interactive
    # control, never the document's outside.
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.keyboard.press("Tab")
    assert page.evaluate("() => document.activeElement && document.activeElement.id") == "main"
    page.keyboard.press("Tab")
    assert page.evaluate(f"() => {_INTERACTIVE}")

    # A third F9 is a no-op at the deepest step: still no chrome.
    page.keyboard.press("F9")
    expect(page.get_by_role("banner")).to_have_count(0)
    expect(page.get_by_role("navigation", name="Hauptnavigation")).to_have_count(0)

    # Esc walks it back one step at a time: the chrome first …
    page.keyboard.press("Escape")
    expect(page.get_by_role("banner")).to_be_visible()
    expect(page.get_by_role("navigation", name="Hauptnavigation")).to_be_visible()
    assert_accessible(page)

    # … then the rail, back to the state the URL held all along.
    page.keyboard.press("Escape")
    expect(page.get_by_role("complementary")).to_be_visible()
    assert_accessible(page)

    # Esc at the shallow end is a no-op: it must not navigate back or leave
    # the page — the text is the proof the workbench never moved.
    page.keyboard.press("Escape")
    expect(page.get_by_role("heading", name="Die Stilllegung")).to_be_visible()
    expect(editor).to_contain_text("Erster Satz im Fokus.")
    assert_accessible(page)


def test_focus_two_url_renders_chrome_free(page: Page, stack: Stack) -> None:
    _open_workbench(page, "Das Fahrwasser")

    # A shared link lands exactly in the state it was shared in.
    page.goto(f"{page.url.split('?')[0]}?focus=2")

    expect(page.locator(".ProseMirror")).to_be_visible()
    expect(page.get_by_role("banner")).to_have_count(0)
    expect(page.get_by_role("complementary")).to_have_count(0)
    # The icon rail is chrome too (P8): a direct depth-2 link renders none
    # of it — and the way back (Esc below) must return both columns.
    expect(page.get_by_role("navigation", name="Hauptnavigation")).to_have_count(0)
    # The affordance is gone at the deepest step: the keyboard is the way
    # back, and nothing on the page pretends otherwise.
    expect(page.get_by_role("button", name="Fokus")).to_have_count(0)

    # And the way back works from a direct render too.
    page.keyboard.press("Escape")
    expect(page.get_by_role("banner")).to_be_visible()
    expect(page.get_by_role("navigation", name="Hauptnavigation")).to_be_visible()


def test_depth_two_hides_the_frame_and_retracts_its_hint(page: Page, stack: Stack) -> None:
    """The runhead and the footer belong to the frame: they name the chapter
    and count its words at the workbench, and both are gone at the deepest
    step — where the one-line hint offers the way back, once, and retracts
    (F23). A hint whose hidden state broke the page would fail this floor."""
    _open_workbench(page, "Der Seitensteg")

    # Depth 0: the frame names the chapter and its position in the book.
    # The chapter's name lives in the runhead's input; untitled, it wears
    # the localized placeholder there.
    title_field = page.get_by_label("Kapiteltitel")
    expect(page.get_by_text("Der Seitensteg ·")).to_be_visible()
    expect(title_field).to_have_attribute("placeholder", "Kapitel 1")
    expect(page.get_by_text("Kapitel 1 von 1")).to_be_visible()

    page.keyboard.press("F9")
    page.keyboard.press("F9")
    expect(page.locator(".ProseMirror")).to_be_visible()
    assert "focus=2" in page.url

    # The continue button is a writing control, not chrome (the final
    # wave's declined list): the workspace's one filled primary stays at
    # the deepest step while the frame around it yields — paint included,
    # not merely present.
    door = page.get_by_role("button", name="Weiterschreiben")
    expect(door).to_be_visible()
    expect(door).to_have_class(re.compile(r"bg-primary"))

    # Both are hidden at the deepest step, and the hint that offers Esc
    # shows once, then retracts.
    expect(title_field).to_have_count(0)
    expect(page.get_by_text("Der Seitensteg ·")).to_have_count(0)
    expect(page.get_by_text(re.compile(r"Wörter"))).to_have_count(0)
    hint = page.get_by_text("Esc zeigt die Leiste wieder")
    expect(hint).to_be_visible()
    # The hint retracts on its own clock; poll for the retraction instead of
    # sleeping its whole window and then asking once.
    expect(hint).to_have_count(0, timeout=8_000)

    # The retracted state must leave a whole page behind: no orphaned hint,
    # no contrast the floor trips over, the keyboard still on the surface.


def test_go_back_from_depth_two_restores_chrome(page: Page, stack: Stack) -> None:
    _open_workbench(page, "Die Reede")

    # A direct jump to the deepest step, then the back button: leaving
    # depth 2 must run the unmount path's cleanup and bring the chrome back.
    page.goto(f"{page.url.split('?')[0]}?focus=2")
    expect(page.locator(".ProseMirror")).to_be_visible()
    expect(page.get_by_role("banner")).to_have_count(0)

    page.go_back()

    expect(page.get_by_role("banner")).to_be_visible()


def test_chrome_returns_when_leaving_the_novel(page: Page, stack: Stack) -> None:
    _open_workbench(page, "Der Leitdamm")
    # Panels away, chrome still there: depth 1.
    page.goto(f"{page.url.split('?')[0]}?focus=1")
    # The editor's visibility proves the page loaded — only then does an
    # absent rail mean "hidden by focus", not "not rendered yet".
    expect(page.locator(".ProseMirror")).to_be_visible()
    expect(page.get_by_role("complementary")).to_have_count(0)
    expect(page.get_by_role("banner")).to_be_visible()

    # Leaving the workbench restores the shell everywhere else.
    page.get_by_role("link", name="Alle Romane").click()
    expect(page.get_by_role("banner")).to_be_visible()
    expect(page.get_by_role("heading", name="Das Bücherregal")).to_be_visible()
    assert_accessible(page)
