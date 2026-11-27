# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The Allgemein surface on the real stack (W7 Task 5): the settings
capability's first page, proven over browser, API and Postgres.

The profile round-trip walks the one dirty form's own contract — a pristine
save makes no ask (the wire listener proves the silence, not just the row's
equality), the save carries only the dirtied fields, a carried null clears
and an absent field keeps — and asks the server back after every leg,
so the fields the browser holds and the users row Postgres keeps are proven
to be one truth. The immediate controls ride the existing seams: a language
card re-renders the chrome at once through the one language contract (the
rail's own gear label flips with the page's), the theme cards and the rail's
toggle share the one theme write, and the boot re-adopts what the row keeps —
and no write ever wipes a standing sibling: a language choice keeps the dark
theme, a profile save keeps both, a theme write keeps the profile (the
isolation leg). The user-block menu's doors and the gear in the
rail land on `/settings` at the section addresses, focused; the deep links
are the settings side of the retired Buch-Einstellungen door, whose walk from
the dialog lives in the writing suite (test_workspace_e2e). The offline card
answers the driver read's own word — the default instance's ``fake`` answer
shows it, a provider with a default model makes the instance ``configured``
and hides it — and the refusals keep
every answer: the field's own parse face in the browser, the wire's 422s
asked directly (the UI's contract never sends them — the 422 alert face
itself is the vitest suite's pin). Every face the page shows also clears the
axe WCAG A/AA floor, light and dark, the standing menu included.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, Request, expect

from app.capabilities.settings.e2e.conftest import (
    DATABASE,
    await_settings,
    create_default_model,
    create_provider,
    expect_settings,
    goto_settings,
    patch_settings,
    read_driver,
    read_settings,
    seed_settings,
    set_theme,
)
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.db_rows import rows
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

# The catalog's own words, pinned where a leg leans on them (de-DE context).
HEADING_DE = "Atelier-Einstellungen"
HEADING_EN = "Atelier settings"
HEADING_FR = "Réglages de l'atelier"
LANGUAGE_LABEL_DE = "Oberflächensprache"
NAME_LABEL = "Autorenname"
GOAL_LABEL = "Tagesziel (Wörter)"
SAVE = "Änderungen speichern"
DISCARD = "Verwerfen"
DIRTY = "Ungespeicherte Eingaben"
NEUTRAL_HINT = "Leerlassen, um den neutralen Bezeichner des Ateliers zu behalten."
GOAL_INVALID = "Das Tagesziel muss eine ganze Zahl zwischen 1 und 2.147.483.647 sein."
FOLLOW_DE = "Dem Browser folgen (Spracherkennung beim Start)"
FOLLOW_EN = "Follow the browser (language detection at start)"
FOLLOW_FR = "Suivre le navigateur (détection de la langue au démarrage)"
OFFLINE_TITLE = "Offline-Kompensation"
OFFLINE_BODY = "Lokaler Fake-Treiber aktiv. Eingaben verbleiben auf diesem Rechner."
MENU_TRIGGER = re.compile(r"^Benutzerprofil:")
RAIL_THEME_SYSTEM = "Erscheinungsbild: System. Wechseln zu Hell."


def _author(page: Page):
    return page.get_by_label(NAME_LABEL)


def _goal(page: Page):
    return page.get_by_label(GOAL_LABEL)


def _user_row() -> list[tuple[object, ...]]:
    """The users row as Postgres keeps it — the form's baseline of truth."""
    return rows(
        DATABASE,
        "SELECT locale, theme, author_name, daily_goal_words FROM users WHERE id = :id",
        {"id": str(LOCAL_USER_ID)},
    )


def test_the_profile_round_trip_lands_on_the_row(page: Page, installed: Stack) -> None:
    """Pristine → no ask; dirtied fields only → the row; the carried null
    clears the name while the absent goal keeps — the wire contract read
    back from the API and from Postgres, not from the form."""
    goto_settings(page)

    # The fresh instance's honest empty: the fields open empty, the neutral
    # hint answers the email-less row, the offline card tells the truth.
    expect(_author(page)).to_have_value("")
    expect(_goal(page)).to_have_value("")
    expect(page.get_by_text(NEUTRAL_HINT)).to_be_visible()
    expect(page.get_by_text(OFFLINE_TITLE)).to_be_visible()
    expect(page.get_by_text(DIRTY)).to_have_count(0)

    # The pristine save rests: no diff, no ask — the row stays as it was,
    # and the wire listener heard nothing reach /api at all (the silence is
    # heard, not inferred from the row's equality).
    api_asks: list[str] = []

    def _record_asks(request: Request) -> None:
        if "/api/" in request.url:
            api_asks.append(f"{request.method} {request.url}")

    page.on("request", _record_asks)
    page.get_by_role("button", name=SAVE).click()
    page.wait_for_timeout(300)  # a beat: a bug's ask would fire inside it
    page.remove_listener("request", _record_asks)
    assert api_asks == [], f"the pristine save asked the wire: {api_asks}"
    row = read_settings()
    assert row["author_name"] is None
    assert row["daily_goal_words"] is None

    # The one dirty form: both fields dirtied ride together in one save, the
    # goal as the grouped de figure („1.000" parses to 1000).
    _author(page).fill("Erika Quell")
    expect(page.get_by_text(DIRTY)).to_be_visible()
    _goal(page).fill("1.000")
    page.get_by_role("button", name=SAVE).click()
    expect(page.get_by_text(DIRTY)).to_have_count(0)
    # The saved truth stands in the fields: the goal reads back the grouped
    # figure — the local PATCH answers inside one frame, so a busy-window
    # wait would race it (the writing suite's finding).
    expect(_author(page)).to_have_value("Erika Quell")
    expect(_goal(page)).to_have_value("1.000")

    # The server's own row — the browser wrote what the API keeps, and the
    # users row in Postgres is the same truth.
    await_settings(author_name="Erika Quell", daily_goal_words=1000)
    assert _user_row() == [(None, None, "Erika Quell", 1000)]

    # The carried null clears the name; the goal rides absent and keeps.
    _author(page).fill("")
    page.get_by_role("button", name=SAVE).click()
    expect(page.get_by_text(DIRTY)).to_have_count(0)
    await_settings(author_name=None, daily_goal_words=1000)
    expect(page.get_by_text(NEUTRAL_HINT)).to_be_visible()
    expect(_goal(page)).to_have_value("1.000")
    assert _user_row() == [(None, None, None, 1000)]
    assert_accessible(page)


def test_the_language_cards_flip_at_once_and_carry_the_wire(page: Page, installed: Stack) -> None:
    """A choice re-renders the chrome before the answer lands (the one
    language contract), the write carries {locale} alone, „Dem Browser
    folgen" is the stored null the row keeps, and the radio marks the
    resolved language — the browser's, while the row holds none."""
    goto_settings(page)
    expect(page.get_by_role("heading", name=HEADING_DE)).to_be_visible()

    # The fresh row holds no choice: the checkbox is the stored null's face,
    # the radio marks the resolved Deutsch — the browser's de-DE.
    follow = page.get_by_role("checkbox", name=FOLLOW_DE)
    expect(follow).to_be_checked()
    expect(page.get_by_role("radio", name="Deutsch")).to_be_checked()

    # English: the heading flips AT ONCE, then the PATCH answers — the wire
    # carries the locale alone, and the checkbox ends (the row holds a
    # choice now). The card's visible face is clicked, not the sr-only
    # input beneath it. The re-render reaches the whole chrome: the rail's
    # own gear label flips with the page's — the chrome speaks the choice,
    # not just the surface.
    page.get_by_text("English", exact=True).click()
    expect(page.get_by_role("heading", name=HEADING_EN)).to_be_visible()
    rail = page.locator("aside").filter(has=page.get_by_role("navigation", name="Navigation"))
    expect(rail.get_by_role("link", name="Settings")).to_be_visible()
    await_settings(locale="en")
    assert read_settings()["theme"] is None  # one mechanism: no theme ride-along
    follow_en = page.get_by_role("checkbox", name=FOLLOW_EN)
    expect(follow_en).not_to_be_checked()

    # Storing Deutsch ends nothing — the checkbox stays off, the row keeps
    # the choice (a checked radio's re-click is no transition, so every
    # card click here is a real change).
    page.get_by_text("Deutsch", exact=True).click()
    await_settings(locale="de")
    expect(page.get_by_role("checkbox", name=FOLLOW_DE)).not_to_be_checked()

    # English again over the stored choice, then „Dem Browser folgen": the
    # carried null hands the choice back — German answers at once, the row
    # keeps the null, Deutsch is the resolved face, and the rail's gear
    # label walks back with it.
    page.get_by_text("English", exact=True).click()
    await_settings(locale="en")
    follow_en.check()
    expect(page.get_by_role("heading", name=HEADING_DE)).to_be_visible()
    await_settings(locale=None)
    expect(rail.get_by_role("link", name="Einstellungen")).to_be_visible()
    follow = page.get_by_role("checkbox", name=FOLLOW_DE)
    expect(follow).to_be_checked()
    expect(page.get_by_role("radio", name="Deutsch")).to_be_checked()


def test_the_language_cards_follow_the_registry_order(page: Page, installed: Stack) -> None:
    goto_settings(page)
    expect(page.get_by_role("heading", name=HEADING_DE)).to_be_visible()

    cards = page.get_by_role("radiogroup", name=LANGUAGE_LABEL_DE).get_by_role("radio")
    expect(cards).to_have_count(3)
    assert [card.get_attribute("aria-label") for card in cards.all()] == [
        "Deutsch",
        "English",
        "Français",
    ]


def test_a_language_is_loaded_only_when_it_is_read(page: Page, installed: Stack) -> None:
    asked: list[str] = []
    page.on("request", lambda request: asked.append(request.url))
    goto_settings(page)
    expect(page.get_by_role("heading", name=HEADING_DE)).to_be_visible()
    page.get_by_text("Français", exact=True).click()
    expect(page.get_by_role("heading", name=HEADING_FR)).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name=HEADING_FR)).to_be_visible()
    await_settings(locale="fr")

    def module_requests(code: str) -> int:
        return sum(1 for url in asked if f"/lib/generated/catalogs/{code}.ts" in url)

    assert module_requests("de") >= 1, "the browser's language is fetched when it is read"
    assert module_requests("fr") >= 1, "a switched-to language is fetched when it is read"
    assert module_requests("en") == 0, "the source language is bundled, never fetched"
    # The catalog loads before the choice applies, so the controlled state
    # settles a moment after the click; following the browser also renames
    # the checkbox to the browser's language, so assert the landed face.
    page.get_by_role("checkbox", name=FOLLOW_FR).click()
    expect(page.get_by_role("checkbox", name=FOLLOW_DE)).to_be_checked()
    await_settings(locale=None)


def test_the_theme_flips_persists_and_shares_the_one_seam(page: Page, installed: Stack) -> None:
    """A card applies at once, PATCHes the theme's own door and survives the
    boot's adoption; the row's null is the system's own; and the rail's
    toggle rides the same seam — its write marks the page's card."""
    goto_settings(page)

    # The fresh row keeps no theme: the system card is the checked face, the
    # document wears no theme (the de-DE context's light system).
    expect(page.get_by_role("radio", name="Systemstandard")).to_be_checked()
    expect(page.locator("html")).not_to_have_attribute("data-theme", ".+")

    # Dunkel: at once on the document, then the theme door answers — the
    # card's visible face is clicked, not the sr-only input beneath it.
    page.get_by_text("Dunkel (Tinte)", exact=True).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    await_settings(theme="dark")
    expect(page.get_by_role("radio", name="Dunkel (Tinte)")).to_be_checked()

    # It persists: a fresh boot adopts the row's choice.
    page.reload()
    expect_settings(page)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_role("radio", name="Dunkel (Tinte)")).to_be_checked()

    # Systemstandard: the carried null — the attribute goes, the row keeps
    # the null, the system card is the checked face again.
    page.get_by_text("Systemstandard", exact=True).click()
    expect(page.locator("html")).not_to_have_attribute("data-theme", ".+")
    await_settings(theme=None)
    expect(page.get_by_role("radio", name="Systemstandard")).to_be_checked()

    # The rail's toggle shares the seam: system → Hell lands on the wire and
    # marks the page's card — no second mechanism.
    page.get_by_role("button", name=RAIL_THEME_SYSTEM).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    await_settings(theme="light")
    expect(page.get_by_role("radio", name="Hell (Pergament)")).to_be_checked()


def test_the_doors_land_focused_on_the_addresses(page: Page, installed: Stack) -> None:
    """The gear in the rail opens `/settings` and wears the active face; the
    user-block menu's doors walk to the two section addresses and the focus
    lands on the field each names — on a same-page walk and on a fresh load,
    the settings side of the retired Buch-Einstellungen door (whose walk
    from the dialog is the writing suite's)."""
    seed_settings(author_name="Erika Quell")

    # The addresses themselves: a fresh load at the goal's address boots
    # straight into the field's focus — the landing is the field, not just a
    # scroll. (A fragment-only goto is a same-document hash change the
    # router does not observe, so the second address is walked through the
    # real doors below — the router's own navigate, exactly what the menu
    # rows and the retired dialog's door call.)
    page.goto(f"{BASE}/settings#tagesziel-feld")
    expect(_goal(page)).to_be_focused()

    # The gear door: live with no book standing (the one global one), the
    # active face on the route it stands on.
    page.goto(f"{BASE}/")
    rail = page.locator("aside").filter(has=page.get_by_role("navigation", name="Navigation"))
    gear = rail.get_by_role("link", name="Einstellungen")
    expect(gear).to_have_attribute("href", "/settings")
    gear.click()
    expect(page).to_have_url(f"{BASE}/settings")
    expect(page.get_by_test_id("settings-page")).to_be_visible()
    expect(gear).to_have_attribute("aria-current", "page")

    # The user block's menu: the trigger names the stored author, the
    # initials chip's glyphs carried in the name (the switcher's contract).
    trigger = page.get_by_role("button", name=MENU_TRIGGER)
    expect(trigger).to_have_accessible_name("Benutzerprofil: EQ Erika Quell")

    # Autorenname bearbeiten → the profile section's address, focused.
    def open_menu() -> None:
        trigger.click()
        expect(page.get_by_role("menu", name="Benutzerprofil")).to_be_visible()

    open_menu()
    page.get_by_role("menuitem", name="Autorenname bearbeiten").click()
    expect(page).to_have_url(f"{BASE}/settings#profil-sektion")
    expect(_author(page)).to_be_focused()

    # Tagesziel festlegen → the goal field's address — the same-page door
    # the menu walks while the page stands.
    open_menu()
    page.get_by_role("menuitem", name="Tagesziel festlegen").click()
    expect(page).to_have_url(f"{BASE}/settings#tagesziel-feld")
    expect(_goal(page)).to_be_focused()

    # The Einstellungen row wears the Aktiv face on its own surface and
    # walks there from anywhere.
    open_menu()
    settings_row = page.get_by_role("menuitem", name="Einstellungen")
    expect(settings_row).to_contain_text("Aktiv")
    expect(settings_row).to_have_attribute("aria-current", "true")
    settings_row.click()
    expect(page).to_have_url(f"{BASE}/settings")
    expect_settings(page)

    # The standing menu on the light face clears the same floor — the
    # disabled row's and the badge's inks included.
    open_menu()
    assert_accessible(page)
    page.keyboard.press("Escape")
    expect(page.get_by_role("menu", name="Benutzerprofil")).to_have_count(0)
    assert_accessible(page)


def test_the_offline_card_answers_the_driver_read(page: Page, installed: Stack) -> None:
    """The card stands only while the driver read answers ``fake`` — the
    default instance's own answer — and hides once a provider with the
    default model makes the instance configured; the driver read's word is
    the card's truth, asked directly. No configured endpoint is contacted:
    the read is pure resolution."""
    goto_settings(page)
    expect(page.get_by_text(OFFLINE_TITLE)).to_be_visible()
    expect(page.get_by_text(OFFLINE_BODY)).to_be_visible()

    assert read_driver() == {"kind": "fake"}

    # A provider and its default model: the cascade's default leg answers
    # every routed key through it — the instance is configured, and the
    # card's claim is no longer true.
    provider_id = create_provider()
    create_default_model(provider_id)
    assert read_driver() == {"kind": "configured"}

    # The page asks again on a fresh load: the card is gone.
    page.reload()
    expect_settings(page)
    expect(page.get_by_text(OFFLINE_TITLE)).to_have_count(0)


def test_the_refusals_keep_every_answer(page: Page, installed: Stack) -> None:
    """The unparseable goal answers on its field and writes nothing; the
    wire refuses a locale outside the catalog and a goal out of bounds with
    422s and keeps every stored answer — the lossless refusal the page's
    alert face names (that face itself cannot be driven over the real stack,
    because the form's contract never sends such a shape; the vitest suite
    pins it)."""
    goto_settings(page)

    # The field's own parse face: the save refuses pre-wire, nothing lands.
    _author(page).fill("Erika Quell")
    _goal(page).fill("abc")
    page.get_by_role("button", name=SAVE).click()
    expect(page.get_by_role("alert")).to_contain_text(GOAL_INVALID)
    row = read_settings()
    assert row["author_name"] is None
    assert row["daily_goal_words"] is None
    expect(_author(page)).to_have_value("Erika Quell")  # a refusal never eats the work

    # Verwerfen retires the answers and the badge.
    page.get_by_role("button", name=DISCARD).click()
    expect(_author(page)).to_have_value("")
    expect(page.get_by_text(DIRTY)).to_have_count(0)

    # The wire's own refusals, asked directly — a bad locale and an
    # out-of-bounds goal are 422s, and the row keeps what it kept.
    refused = patch_settings({"locale": "xx"})
    assert refused.status_code == 422
    refused = patch_settings({"locale": None, "daily_goal_words": 0})
    assert refused.status_code == 422
    row = read_settings()
    assert row["locale"] is None
    assert row["author_name"] is None
    assert row["daily_goal_words"] is None

    # The page answers the row's truth still — a reload, the honest empty.
    page.reload()
    expect_settings(page)
    expect(_author(page)).to_have_value("")
    expect(_goal(page)).to_have_value("")
    expect(page.get_by_text(DIRTY)).to_have_count(0)


def test_the_writes_never_wipe_a_standing_sibling(page: Page, installed: Stack) -> None:
    """The three writes are three doors, not one switch: a language choice
    leaves the standing theme dark, a profile save leaves the language and
    the theme standing, a theme write leaves the profile standing — every
    sibling read back from the row it lives on, after the write landed."""
    set_theme("dark")
    seed_settings(locale="en")
    goto_settings(page)
    expect(page.get_by_role("heading", name=HEADING_EN)).to_be_visible()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    # The language write over the standing theme: Deutsch lands, the dark
    # boot stays on the document and on the row.
    page.get_by_text("Deutsch", exact=True).click()
    expect(page.get_by_role("heading", name=HEADING_DE)).to_be_visible()
    await_settings(locale="de", theme="dark")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    # The profile save over both: the name and the goal land, and the row's
    # language and theme are exactly what they were.
    _author(page).fill("Erika Quell")
    _goal(page).fill("500")
    page.get_by_role("button", name=SAVE).click()
    expect(page.get_by_text(DIRTY)).to_have_count(0)
    await_settings(author_name="Erika Quell", daily_goal_words=500, locale="de", theme="dark")

    # The theme write over the standing profile: the carried null lands on
    # the theme door alone, the profile and the language keep their answers.
    page.get_by_text("Systemstandard", exact=True).click()
    await_settings(theme=None, author_name="Erika Quell", daily_goal_words=500, locale="de")
    expect(page.locator("html")).not_to_have_attribute("data-theme", ".+")


def test_the_dark_settings_clear_the_axe_floor(page: Page, installed: Stack) -> None:
    """The surface and the standing user menu on the tokens' dark halves —
    the same WCAG A/AA floor the light face clears, with the dark boot
    adopted from the row and an author name standing, so the initials
    chip's text face and the label-in-name trigger are floored too. No
    exclusion: the menu's inks ride the pairs the tokens gate pins (the
    muted row over the lowest ground, the muted badge on the card
    ground)."""
    set_theme("dark")
    seed_settings(author_name="Erika Quell")
    goto_settings(page)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    assert_accessible(page)

    trigger = page.get_by_role("button", name=MENU_TRIGGER)
    expect(trigger).to_have_accessible_name("Benutzerprofil: EQ Erika Quell")
    trigger.click()
    expect(page.get_by_role("menu", name="Benutzerprofil")).to_be_visible()
    assert_accessible(page)
