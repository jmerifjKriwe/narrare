"""The zen room on the real stack (W4 Task 21, the fidelity gate).

F9 clears the desk (D19): the page swaps the workspace's columns for the room,
the scene's prose stands centered under the manuscript head, and the
Absatz-/Satz-/Normal dimming cycles frontend-real (D6) on the one live editor.
Esc exits and returns the desk's focus; the ghost owns Esc BEFORE the room (the
order Task 18 pinned at unit level, pinned here on the real face). The counters
and the pomodoro are real and session-only — a re-entry starts fresh, nothing
is stored. The soundscape stays disabled with its drafted note (#877), and no
sepia control ships (D18).

The axe floor (design §10) reads the room honestly in both themes. The draft's
dimming is the ONE sanctioned below-AA ink — the feature itself, an owner
decision (D6 frontend-real; Task 18 deviation 8) — so the contrast exemption is
pinned narrowly to the dim nodes and must be exercised. Normal mode dimms
nothing and clears the whole floor unaided; the room's chrome (spines, eyebrow,
divider, end mark, presets) rides at floor-clearing strength after Task 21's
fidelity pass (the PR4 ghost-ink discipline, gap ledger).
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.writing.e2e.conftest import (
    create_chapter,
    create_novel,
    set_daily_goal,
    set_theme,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL
PROSE = "Szenenprosa"  # the editor textbox's accessible name
PILL = re.compile("Vorschlag übernehmen")

# The dim is the draft's own geometry (zen-focus-2.html:234 — the prose flow's
# `opacity-30 … hover:opacity-50`, „Gedimmte frühere Absätze"), below the AA
# floor by design and the room's one sanctioned exemption (D6, Task 18
# deviation 8). The selector names exactly the decoration plugin's dim classes
# — never the focal card, never the chrome, never the page.
DIM_EXEMPT = ".zen-dim-block, .zen-dim-inline"

# Three real paragraphs, several sentences each, so Absatz-Fokus dims whole
# blocks and Satz-Fokus dims the sentences outside the caret's own.
BODY = (
    "Die Konsole reagierte nicht auf den Transponderchip, sondern auf die Druckkurve "
    "seiner Fingerkuppen auf den kalten Bakelit-Tasten. Aris zählte vier Schläge Pause "
    "zwischen den Relais.\n\n"
    "Irgendwo hinter der Wand summte ein Transformator, der seit drei Jahren nicht "
    "gewartet worden war. Das Summen war der einzige Ton, der noch zur Station gehörte. "
    "Die Kälte roch nach flüssigem Stickstoff.\n\n"
    "Sie legte die Hand auf das Gehäuse und wartete auf das Zeichen, das niemand "
    "vereinbart hatte. Die Nacht draußen war still. Der Frost kroch durch die Fugen."
)
TODAY_WORDS = len(BODY.split())


def _seed_zen_book() -> str:
    """One book, one chapter, one three-paragraph scene — the room's corpus.
    The daily goal stands so the ring's aggregate has a source; the scene's
    overline carries the row's own setting · story_time."""
    novel = create_novel("Der Klang des Eises", genre="Mystery & Noir", target_words=85000)
    chapter = create_chapter(str(novel["id"]), "Nevada Echoes")
    write_scene(
        str(chapter["id"]),
        BODY,
        title="Sub-Basement",
        setting="Forschungsstation 7",
        story_time="27. Oktober 2094, 03:14 UTC",
    )
    set_daily_goal(500)
    return str(novel["id"])


def _enter_zen(page: Page, novel_id: str) -> None:
    """Open the workspace on the seeded scene and F9 into the room."""
    page.goto(f"{BASE}/novels/{novel_id}")
    expect(page.get_by_test_id("explorer-tree")).to_be_visible()
    page.keyboard.press("F9")
    expect(page.get_by_test_id("zen-mode")).to_be_visible()
    # The columns unmount — one live editor at a time (the swap IS the design).
    expect(page.get_by_test_id("explorer-tree")).to_have_count(0)


def test_f9_enters_zen_and_the_prose_stands_centered(page: Page, installed: Stack) -> None:
    """F9 swaps the desk for the room: the prose stands centered under the
    manuscript head (the book eyebrow, the chapter title, the row's own
    overline), the counters read the real aggregate, the pomodoro runs, the
    soundscape stays disabled with its note, and no sepia control ships."""
    novel_id = _seed_zen_book()
    _enter_zen(page, novel_id)

    room = page.get_by_test_id("zen-mode")
    expect(room).to_have_attribute("aria-modal", "true")

    # The prose is centered: the corpus column's horizontal centre is the
    # viewport's own (the draft's 36rem article, items-center).
    viewport = page.viewport_size
    assert viewport is not None
    box = page.get_by_test_id("zen-prose").bounding_box()
    assert box is not None
    centre = box["x"] + box["width"] / 2
    assert abs(centre - viewport["width"] / 2) <= 1, f"prose off-centre: {centre}"

    # The manuscript head — the row's own facts, never the draft's mock line.
    expect(room.get_by_text("Roman · Der Klang des Eises")).to_be_visible()
    expect(room.get_by_role("heading", name="Kapitel 1 — Nevada Echoes")).to_be_visible()
    expect(page.get_by_test_id("zen-overline")).to_have_text(
        "Forschungsstation 7 · 27. Oktober 2094, 03:14 UTC"
    )

    # The counters: today the aggregate's net (the seeded words), session zero.
    expect(room.get_by_text(f"Heute: +{TODAY_WORDS} W · Sitzung: 0 W")).to_be_visible()
    # The pomodoro runs from 25:00 on entry (session-only).
    timer = room.get_by_role("group", name="Pomodoro-Timer")
    expect(timer.get_by_text(re.compile(r"^2[45]:[0-5]\d$"))).to_be_visible()

    # The exit chip carries the Esc keycap; the soundscape is disabled with the
    # drafted note; NO sepia control anywhere (D18).
    expect(room.get_by_role("button", name="Zurück zum Workspace")).to_be_visible()
    expect(room.get_by_text("Esc", exact=True)).to_be_visible()
    soundscape = room.get_by_role("button", name="Klanglandschaften deaktiviert")
    expect(soundscape).to_be_disabled()
    expect(soundscape).to_have_attribute("title", "Noch nicht verfügbar.")
    expect(room.get_by_role("button", name=re.compile("Sepia"))).to_have_count(0)

    # Absatz-Fokus is the entry mode — the focal card stands, the rest dim.
    expect(page.locator(".zen-active-block")).to_have_count(1)
    expect(page.locator(".zen-dim-block")).to_have_count(2)
    assert_accessible(page, contrast_exempt_selector=DIM_EXEMPT)


def test_the_dimming_cycles_the_three_presets(page: Page, installed: Stack) -> None:
    """Absatz dims whole blocks around the focal card; Satz dims the inline
    sentences outside the caret's own; Normal dimms nothing. The segment's
    aria-pressed follows, and each face clears its honest axe floor."""
    novel_id = _seed_zen_book()
    _enter_zen(page, novel_id)
    presets = page.get_by_role("group", name="Fokus-Modus")

    # Absatz-Fokus (entry): one focal card, the other blocks dimmed.
    expect(presets.get_by_role("button", name="Absatz-Fokus", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".zen-active-block")).to_have_count(1)
    expect(page.locator(".zen-dim-block")).to_have_count(2)
    expect(page.locator(".zen-dim-inline")).to_have_count(0)
    assert_accessible(page, contrast_exempt_selector=DIM_EXEMPT)

    # Satz-Fokus: inline spans dim the sentences outside the caret's own; the
    # block classes retire.
    presets.get_by_role("button", name="Satz-Fokus", exact=True).click()
    expect(presets.get_by_role("button", name="Satz-Fokus", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".zen-dim-inline").first).to_be_visible()
    expect(page.locator(".zen-dim-block")).to_have_count(0)
    assert_accessible(page, contrast_exempt_selector=DIM_EXEMPT)

    # Normal: nothing dimmed — the whole floor, no exemption (the chrome must
    # clear AA unaided, and the exemption would be stale here).
    presets.get_by_role("button", name="Normal", exact=True).click()
    expect(presets.get_by_role("button", name="Normal", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".zen-dim-block")).to_have_count(0)
    expect(page.locator(".zen-dim-inline")).to_have_count(0)
    expect(page.locator(".zen-active-block")).to_have_count(0)
    assert_accessible(page)


def test_esc_and_f9_exit_zen_and_return_the_desk_focus(page: Page, installed: Stack) -> None:
    """Esc exits the room and returns the focus to the ribbon door that opened
    it; F9 toggles both ways; the ribbon's Fokus door opens the room too."""
    novel_id = _seed_zen_book()
    page.goto(f"{BASE}/novels/{novel_id}")
    expect(page.get_by_test_id("explorer-tree")).to_be_visible()

    # The ribbon door opens the room (its interim ended in Task 18).
    door = page.get_by_role("button", name="Fokus (F9)", exact=True)
    door.click()
    expect(page.get_by_test_id("zen-mode")).to_be_visible()

    # Esc exits; the columns return and the focus lands back on the door.
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("zen-mode")).to_have_count(0)
    expect(page.get_by_test_id("explorer-tree")).to_be_visible()
    expect(page.locator("#workspace-focus-door")).to_be_focused()

    # F9 toggles on and off (D19), the focus return holding on the F9 exit too.
    page.keyboard.press("F9")
    expect(page.get_by_test_id("zen-mode")).to_be_visible()
    page.keyboard.press("F9")
    expect(page.get_by_test_id("zen-mode")).to_have_count(0)
    expect(page.locator("#workspace-focus-door")).to_be_focused()
    assert_accessible(page)


def test_the_ghost_owns_esc_before_the_room(page: Page, installed: Stack) -> None:
    """The ghost-first Esc order on the real face (Task 18 pinned it at unit
    level): with a proposal standing in the room, the first Esc dismisses the
    ghost and the room STANDS; the second Esc exits the room. The fake provider
    is the one permitted boundary fake (rule 2)."""
    novel_id = _seed_zen_book()
    _enter_zen(page, novel_id)

    # The bar floats in the room; the bare ask streams the ghost at the tail.
    page.get_by_role("button", name="Weiterschreiben").click()
    expect(page.get_by_role("button", name=PILL)).to_be_visible(timeout=10_000)
    expect(page.get_by_test_id("zen-mode")).to_be_visible()

    # First Esc: the ghost goes, the room stays.
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    expect(page.get_by_test_id("zen-mode")).to_be_visible()

    # Second Esc: the room exits, the desk returns.
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("zen-mode")).to_have_count(0)
    expect(page.get_by_test_id("explorer-tree")).to_be_visible()
    expect(page.locator("#workspace-focus-door")).to_be_focused()


def test_the_timer_and_session_counter_are_session_only(page: Page, installed: Stack) -> None:
    """The pomodoro pauses and resets; the session counter tracks the live net
    delta; nothing is stored — a re-entry starts fresh (timer 25:00, session 0)
    and the browser's storage stays empty of the room."""
    novel_id = _seed_zen_book()
    _enter_zen(page, novel_id)
    room = page.get_by_test_id("zen-mode")
    timer = room.get_by_role("group", name="Pomodoro-Timer")
    clock = timer.get_by_text(re.compile(r"^\d{2}:\d{2}$"))

    # Pause holds the clock; reset returns it to the full 25:00.
    timer.get_by_role("button", name="Timer pausieren").click()
    paused = clock.inner_text()
    page.wait_for_timeout(1200)
    assert clock.inner_text() == paused, "the paused pomodoro kept ticking"
    timer.get_by_role("button", name="Timer zurücksetzen").click()
    expect(clock).to_have_text("25:00")

    # The session counter tracks the writer's own net delta since entry.
    expect(room.get_by_text(f"Heute: +{TODAY_WORDS} W · Sitzung: 0 W")).to_be_visible()
    prose = page.get_by_role("textbox", name=PROSE)
    prose.press("Control+End")
    page.keyboard.type(" Eigene Worte am Ende.")
    expect(room.get_by_text("Sitzung: 4 W")).to_be_visible()

    # The room writes no storage of its own (the pomodoro is session-only,
    # design §12) — the pin is defensive: were the room ever to persist, its
    # keys would START with its own state's names (zen, the timer/pomodoro,
    # the session counter, the focus mode). Anchored prefixes, never
    # substrings: a shell key that merely contains one of the words (a future
    # `lastFocus`, say) is not the room's and must not false-fail. The shell's
    # own hints ride `narrare.*` (theme, locale, formality), never these.
    keys = page.evaluate("() => [...Object.keys(localStorage), ...Object.keys(sessionStorage)]")
    room_keys = [k for k in keys if re.search(r"^(zen|timer|pomodoro|session|focus)", k, re.I)]
    assert room_keys == [], f"the zen room wrote to browser storage: {room_keys}"

    # A re-entry starts fresh — the timer full, the session zero again.
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("zen-mode")).to_have_count(0)
    page.keyboard.press("F9")
    expect(page.get_by_test_id("zen-mode")).to_be_visible()
    expect(room.get_by_text("Sitzung: 0 W")).to_be_visible()
    expect(timer.get_by_text(re.compile(r"^2[45]:[0-5]\d$"))).to_be_visible()


def test_the_dark_zen_face_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The room on the tokens' dark halves: the dim stays the one sanctioned
    exemption (Absatz), and Normal clears the whole floor unaided."""
    set_theme("dark")
    novel_id = _seed_zen_book()
    _enter_zen(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(22, 20, 15)"

    expect(page.locator(".zen-dim-block")).to_have_count(2)
    assert_accessible(page, contrast_exempt_selector=DIM_EXEMPT)

    presets = page.get_by_role("group", name="Fokus-Modus")
    presets.get_by_role("button", name="Normal", exact=True).click()
    expect(page.locator(".zen-dim-block")).to_have_count(0)
    assert_accessible(page)
