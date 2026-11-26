"""The setup wizard drives the real stack: browser, API and Postgres.

Every test opens on an uninstalled instance (``e2e/conftest.py`` empties the
database before each one). The welcome offers the three real demos and an
honestly disabled import; the blank path answers every wizard question and
the persisted novel row carries each answer; the demo path keeps the
archive's own identity while the settings bind onto it; a missing title
blocks continue with the drafted message; and the address keeps the wizard's
state until step four posts it — after which a returning visit, in this
browser or a fresh one, lands on the shelf. The database assertions are the
honest check: the screen and the row must agree. Every face the wizard shows
— the welcome, all four steps and the real shelf — also clears the axe WCAG
A/AA floor (``assert_accessible``).
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, expect

from app.capabilities.setup.e2e.conftest import DATABASE
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.db_rows import rows as _shared_rows
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

# The wizard's German face (de-DE context, pinned in app/capabilities/conftest.py).
BASIS_HERO = "Wie möchtest du dein literarisches Werk beginnen?"
CONTINUE_TO_STRUCTURE = "Weiter zu Schritt 2 — Dramaturgie & Struktur"
CONTINUE_TO_AI_RULES = "Weiter zu Schritt 3 — KI-Partner & Kausalitätsregeln"
CONTINUE_TO_PROVISIONING = "Weiter zu Schritt 4 — Bereitstellung & Start"
TITLE_MISSING = "Ein Arbeitstitel fehlt noch — er trägt dein Werk bis zur ersten Seite."
BACK_TO_SHELF = "Zurück zur Bibliotheksübersicht"

# The real shelf the writing capability shows at `/` once the instance is
# set up (Task 6's port of the shelf draft family). The welcome moved to
# `/setup` with the W3 handover; the shelf's own contract lives in
# ShelfPage.test and the writing E2E suite.
SHELF_TITLE = "Das Bücherregal"

# The bundled archive's own facts (app/kernel/interchange/demos/im-stillen-wald):
# the demo path must land exactly these, never the typed ones.
DEMO_TITLE = "Im Stillen Wald"
DEMO_GENRE = "Literary"
DEMO_CHAPTERS = ["Das Flüstern im Wald", "Die Grenze zwischen Welten"]
DEMO_ENTITY_COUNT = 6
DEMO_RELATION_COUNT = 3


def _rows(statement: str, params: dict[str, object] | None = None) -> list[tuple[object, ...]]:
    """Thin wrapper over the shared reader (app/kernel/testing/db_rows)."""
    return _shared_rows(DATABASE, statement, params)


def test_welcome_offers_the_three_real_demos_and_an_honest_import(page: Page, stack: Stack) -> None:
    """Spec (a): an uninstalled instance's `/` redirects to `/setup`, where the
    welcome opens — the three bundled demos as real doors into the wizard, the
    import honestly disabled."""
    page.goto(BASE + "/")

    # The unconfigured `/` hands off to setup's door; the welcome renders there.
    expect(page).to_have_url(BASE + "/setup")
    expect(
        page.get_by_role("heading", name="Tritt ein. Dein ungeschriebenes Werk wartet.")
    ).to_be_visible()
    expect(page).to_have_title("Willkommen im Atelier — Narrare")

    # Each demo is the archive's own title and facts, and a door into the
    # wizard with its world preselected.
    for slug, title, genre, chapters in (
        ("dead-signal", "Dead Signal", "Science Fiction", 7),
        ("echoes-of-the-thornwall", "Echoes of the Thornwall", "Fantasy", 4),
        ("im-stillen-wald", "Im Stillen Wald", "Literary", 2),
    ):
        entry = page.get_by_role("link", name=f"»{title}«")
        expect(entry).to_be_visible()
        expect(entry).to_contain_text(f"{genre} • {chapters} Kap.")
        expect(entry).to_have_attribute("href", f"/setup/basis?demo={slug}")

    # The wizard's own door, and the import that does not exist yet.
    expect(page.get_by_role("link", name="Atelier einrichten")).to_have_attribute(
        "href", "/setup/basis"
    )
    expect(
        page.get_by_role("button", name="Manuskript importieren (.docx, .scriv)")
    ).to_be_disabled()
    expect(page.get_by_text("kommt mit dem weiteren Aufbau")).to_be_visible()

    assert_accessible(page)


def test_the_blank_path_binds_every_answer_into_the_novel_row(page: Page, stack: Stack) -> None:
    """Spec (b): title, two genre pills, target, typology, form, role and canon
    through all four steps — the provisioning checklist shows the facts, the
    way home leads to the real shelf, and the persisted row carries every
    answer."""
    page.goto(BASE + "/")
    expect(page).to_have_url(BASE + "/setup")
    page.get_by_role("link", name="Atelier einrichten").click()
    expect(page).to_have_url(re.compile(r"/setup/basis$"))
    expect(page.get_by_role("heading", name=BASIS_HERO)).to_be_visible()

    # Step 1 — the blank canvas: a title, two genres, a word target.
    page.get_by_label("Arbeitstitel des Manuskripts").fill("Der Klang des Eises")
    page.get_by_role("button", name="Mystery & Noir", exact=True).click()
    page.get_by_role("button", name="Literarische Belletristik", exact=True).click()
    expect(page.get_by_role("button", name="Mystery & Noir", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    page.get_by_label("Ziel-Umfang des Manuskripts").fill("80000")
    page.get_by_role("button", name=CONTINUE_TO_STRUCTURE, exact=True).click()

    # Step 2 — the mental model and the paradigm.
    expect(page).to_have_url(re.compile(r"/setup/structure"))
    page.get_by_role("radio", name="Der Hybrid (Plantser)").check()
    page.get_by_role("radio", name="Die Heldenreise").check()
    assert_accessible(page)
    page.get_by_role("button", name=CONTINUE_TO_AI_RULES, exact=True).click()

    # Step 3 — the partner's role and the canon's strictness (3 → 4).
    expect(page).to_have_url(re.compile(r"/setup/ai-rules"))
    page.get_by_role("radio", name="Sokratischer Lektor").check()
    canon = page.get_by_role("slider", name="Kanon-Strenge")
    expect(canon).to_have_value("3")
    canon.press("ArrowRight")
    expect(canon).to_have_value("4")
    assert_accessible(page)
    page.get_by_role("button", name=CONTINUE_TO_PROVISIONING, exact=True).click()

    # Step 4 — the one POST lands, and the checklist is the response's facts.
    expect(page).to_have_url(re.compile(r"/setup/provisioning"))
    expect(
        page.get_by_role("heading", name="Dein Atelier für „Der Klang des Eises“ wird gebunden.")
    ).to_be_visible()
    expect(page.get_by_text("Bereit zur Manuskript-Initialisierung")).to_be_visible()
    expect(page.get_by_text("Roman-Basis & Metadaten geladen")).to_be_visible()
    expect(
        page.get_by_text("Mystery & Noir, Literarische Belletristik • Die Heldenreise")
    ).to_be_visible()
    expect(page.get_by_text("Kapitelstruktur angelegt")).to_be_visible()
    expect(page.get_by_text("0 Kapitel bereit")).to_be_visible()
    expect(page.get_by_text("Tonalitäts-Matrix & Kausalitätswächter aktiv")).to_be_visible()
    expect(page.get_by_text("Sokratischer Lektor", exact=True)).to_be_visible()
    expect(page.get_by_text("Satzspiegel & Typografie kalibriert")).to_be_visible()
    expect(page.get_by_text("Bereit (100 %)")).to_be_visible()
    assert_accessible(page)

    # The shelf takes the root: the way home leads to the real shelf, and
    # its hero speaks the bound novel's own title and target — the row's
    # facts, never the draft's mock. The row below remains the honest check.
    page.get_by_role("link", name=BACK_TO_SHELF).click()
    expect(page).to_have_url(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    # Exact reads: the activity banner's goal line names the book too
    # (Task 10) — the hero's own heading and word pair are the exact faces.
    expect(page.get_by_role("heading", name="Der Klang des Eises", exact=True)).to_be_visible()
    expect(page.get_by_text("/ 80.000 Wörter", exact=True)).to_be_visible()
    assert_accessible(page)

    # The honest check: the row carries every answer — the joined genres, the
    # target, and all four wizard settings beside them.
    assert _rows(
        "SELECT title, genre, target_words, author_typology, dramatic_form,"
        " ai_role, canon_strictness FROM novels"
    ) == [
        (
            "Der Klang des Eises",
            "Mystery & Noir, Literarische Belletristik",
            80000,
            "plantser",
            "heros-journey",
            "lektor",
            4,
        )
    ]
    # The blank path writes the novel and nothing else.
    assert _rows("SELECT id FROM chapters") == []
    assert _rows("SELECT id FROM entities") == []
    assert len(_rows("SELECT id FROM users")) == 1


def test_the_demo_path_keeps_the_archives_identity_and_binds_the_settings(
    page: Page, stack: Stack
) -> None:
    """Spec (c): the demo card locks title and genre to the archive; the POST
    carries the slug, the way home leads to the real shelf, and the
    settings bind onto the imported novel — chapters and knowledge included."""
    page.goto(BASE + "/")
    expect(page).to_have_url(BASE + "/setup")
    page.get_by_role("link", name=f"»{DEMO_TITLE}«").click()
    expect(page).to_have_url(re.compile(r"/setup/basis\?demo=im-stillen-wald"))

    # Panel 2: the archive's identity, visibly locked — never silently dropped.
    bound_title = page.get_by_label("Arbeitstitel (gebunden)")
    expect(bound_title).to_be_disabled()
    expect(bound_title).to_have_value(DEMO_TITLE)
    bound_genre = page.get_by_label("Genre (gebunden)")
    expect(bound_genre).to_be_disabled()
    expect(bound_genre).to_have_value(DEMO_GENRE)
    expect(
        page.get_by_text(
            "Titel und Genre stammen aus der Vorlage — deine Einstellungen aus "
            "Schritt 2 und 3 gelten zusätzlich."
        )
    ).to_be_visible()
    assert_accessible(page)
    page.get_by_role("button", name=CONTINUE_TO_STRUCTURE, exact=True).click()

    # The settings are the user's own, on the demo path too.
    expect(page).to_have_url(re.compile(r"/setup/structure"))
    page.get_by_role("radio", name="Der Architekt (Plotter)").check()
    page.get_by_role("radio", name="Klassischer 3-Akt-Bogen").check()
    assert_accessible(page)
    page.get_by_role("button", name=CONTINUE_TO_AI_RULES, exact=True).click()
    expect(page).to_have_url(re.compile(r"/setup/ai-rules"))
    page.get_by_role("radio", name="Stiller Archivar & Faktenchecker").check()
    canon = page.get_by_role("slider", name="Kanon-Strenge")
    canon.press("End")
    expect(canon).to_have_value("5")
    assert_accessible(page)
    page.get_by_role("button", name=CONTINUE_TO_PROVISIONING, exact=True).click()

    # The bound checklist: the archive's genre, its chapters, the user's settings.
    expect(page).to_have_url(re.compile(r"/setup/provisioning"))
    expect(
        page.get_by_role("heading", name=f"Dein Atelier für „{DEMO_TITLE}“ wird gebunden.")
    ).to_be_visible()
    expect(page.get_by_text(f"{DEMO_GENRE} • Klassischer 3-Akt-Bogen")).to_be_visible()
    expect(page.get_by_text("Kapitelstruktur der Vorlage übernommen")).to_be_visible()
    expect(page.get_by_text("2 Kapitel bereit")).to_be_visible()
    expect(page.get_by_text("Stiller Archivar & Faktenchecker", exact=True)).to_be_visible()
    assert_accessible(page)

    # The shelf takes the root: the way home leads to the real shelf, and
    # its hero speaks the archive's own identity. The rows below remain the
    # honest check.
    page.get_by_role("link", name=BACK_TO_SHELF).click()
    expect(page).to_have_url(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    expect(page.get_by_role("heading", name=DEMO_TITLE, exact=True)).to_be_visible()
    assert_accessible(page)

    # The honest check: the archive's identity wins, the settings bind onto it,
    # and the demo's chapters and knowledge landed with it. The word target is
    # the wizard's standing default — the demo path posts it like every path.
    assert _rows(
        "SELECT title, author, genre, language, target_words, author_typology,"
        " dramatic_form, ai_role, canon_strictness FROM novels"
    ) == [
        (DEMO_TITLE, "Narrare Demo", DEMO_GENRE, "de", 65000, "plotter", "three-act", "archivar", 5)
    ]
    assert _rows("SELECT title, position FROM chapters ORDER BY position") == [
        (DEMO_CHAPTERS[0], 0),
        (DEMO_CHAPTERS[1], 1),
    ]
    assert len(_rows("SELECT id FROM entities")) == DEMO_ENTITY_COUNT
    assert len(_rows("SELECT id FROM entity_relations")) == DEMO_RELATION_COUNT


def test_a_missing_title_blocks_continue_with_the_drafted_message(page: Page, stack: Stack) -> None:
    """Spec (d): no title, no continue — the drafted message says why, and a
    whitespace-only entry is no title either. Nothing is posted meanwhile."""
    page.goto(BASE + "/setup/basis")
    expect(page).to_have_url(re.compile(r"/setup/basis$"))

    title = page.get_by_label("Arbeitstitel des Manuskripts")
    expect(title).to_have_attribute("aria-invalid", "true")
    expect(page.get_by_text(TITLE_MISSING)).to_be_visible()
    continue_button = page.get_by_role("button", name=CONTINUE_TO_STRUCTURE, exact=True)
    expect(continue_button).to_be_disabled()
    assert_accessible(page)

    # Whitespace is not a title: the draft keeps the entry, the block stays.
    title.fill("   ")
    expect(continue_button).to_be_disabled()
    expect(page.get_by_text(TITLE_MISSING)).to_be_visible()
    assert _rows("SELECT id FROM users") == []
    assert _rows("SELECT id FROM novels") == []

    # A real title lifts the block — the message goes, the door opens.
    title.fill("Die Prüferin")
    expect(continue_button).to_be_enabled()
    expect(page.get_by_text(TITLE_MISSING)).to_have_count(0)
    assert_accessible(page)


def test_provisioning_without_a_basis_redirects_and_never_posts(page: Page, stack: Stack) -> None:
    """Spec (e), the honest redirect: step four with an incomplete wizard state
    falls back to step one — the search rides along, and no POST happens."""
    page.goto(BASE + "/setup/provisioning")
    expect(page).to_have_url(re.compile(r"/setup/basis$"))
    expect(page.get_by_role("heading", name=BASIS_HERO)).to_be_visible()
    assert _rows("SELECT id FROM users") == []
    assert _rows("SELECT id FROM novels") == []

    # Settings without a basis are still no basis: the answers survive the
    # redirect, the write does not happen.
    page.goto(BASE + "/setup/provisioning?typology=plotter&form=three-act&role=lektor&canon=4")
    expect(page).to_have_url(re.compile(r"/setup/basis\?"))
    assert "typology=plotter" in page.url
    assert "form=three-act" in page.url
    assert "role=lektor" in page.url
    assert _rows("SELECT id FROM users") == []
    assert _rows("SELECT id FROM novels") == []


def test_the_wizard_state_survives_deep_links_and_a_returning_visit_shows_the_shelf(
    page: Page, stack: Stack, browser: Browser
) -> None:
    """Spec (e): the address is the wizard's memory — a refresh or a deep link
    mid-wizard keeps every answer and posts nothing; step four is the trigger.
    Once bound, `/` shows the real shelf, in this browser and a fresh one;
    `/setup` and a step deep link redirect back to the shelf (an installed
    instance has no wizard)."""
    page.goto(BASE + "/setup/basis")
    page.get_by_label("Arbeitstitel des Manuskripts").fill("Die Rückkehrerin")
    page.get_by_role("button", name=CONTINUE_TO_STRUCTURE, exact=True).click()
    expect(page).to_have_url(re.compile(r"/setup/structure"))
    page.get_by_role("radio", name="Der Entdecker (Pantser)").check()
    page.get_by_role("radio", name="Save the Cat Beat-Sheet").check()

    # A refresh mid-wizard lands on the same step with the same answers.
    page.reload()
    expect(page.get_by_role("radio", name="Der Entdecker (Pantser)")).to_be_checked()
    expect(page.get_by_role("radio", name="Save the Cat Beat-Sheet")).to_be_checked()
    # Nothing has been posted: the state lives in the address alone.
    assert _rows("SELECT id FROM users") == []
    assert _rows("SELECT id FROM novels") == []

    # A deep link to step three carries the answers; a deep link back to step
    # two still finds them — and the role joined them on the way.
    search = page.url.split("?", 1)[1]
    page.goto(f"{BASE}/setup/ai-rules?{search}")
    page.get_by_role("radio", name="Atmosphärischer Co-Autor").check()
    search = page.url.split("?", 1)[1]
    page.goto(f"{BASE}/setup/structure?{search}")
    expect(page.get_by_role("radio", name="Der Entdecker (Pantser)")).to_be_checked()
    expect(page.get_by_role("radio", name="Save the Cat Beat-Sheet")).to_be_checked()
    assert _rows("SELECT id FROM novels") == []

    # Step four is the trigger: arriving with a complete basis posts once.
    search = page.url.split("?", 1)[1]
    page.goto(f"{BASE}/setup/provisioning?{search}")
    expect(
        page.get_by_role("heading", name="Dein Atelier für „Die Rückkehrerin“ wird gebunden.")
    ).to_be_visible()
    assert _rows(
        "SELECT title, author_typology, dramatic_form, ai_role, canon_strictness FROM novels"
    ) == [("Die Rückkehrerin", "pantser", "save-the-cat", "coautor", 3)]

    # The returning visit: the instance remembers, not the browser. The shelf
    # takes the root, and its hero speaks the bound novel on every load.
    page.goto(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    expect(page.get_by_role("heading", name="Die Rückkehrerin", exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()

    # The inverse gate: an installed instance has no wizard. `/setup` and a
    # step deep link both redirect back to the shelf.
    page.goto(BASE + "/setup")
    expect(page).to_have_url(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    page.goto(BASE + "/setup/basis")
    expect(page).to_have_url(BASE + "/")

    # A second browser shares nothing but the API — and lands on the same shelf.
    # The hand-made context repeats the pinned locale (repo convention).
    other_context = browser.new_context(locale="de-DE")
    try:
        other = other_context.new_page()
        other.goto(BASE + "/")
        expect(other.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    finally:
        other_context.close()

    assert_accessible(page)


def test_the_language_contract_rides_one_home_and_the_chrome_frames_only_the_shelf(
    page: Page, stack: Stack
) -> None:
    """W4 Task 10 (D17 / D15, shelf rows 12 / 20): the welcome's and the
    wizard's switchers are the shared contract's pre-setup faces — the
    choice applies at once, the structural 409 keeps the mirror, a refresh
    speaks it without a write — and the guided flows stand chrome-less.
    Once bound, the shelf wears the app-wide chrome, the provisioning seam
    carries the mirror into the row, and the row is the language's record."""
    page.goto(BASE + "/")
    expect(page).to_have_url(BASE + "/setup")

    # The welcome stands alone: no rail nav, no topbar search chip.
    expect(page.get_by_role("navigation", name="Navigation")).to_have_count(0)
    expect(page.get_by_role("button", name="Suchen")).to_have_count(0)

    # The pre-setup switcher: English applies at once; the row cannot hold
    # it yet (409), the mirror keeps it across a refresh — nothing installed.
    page.get_by_role("radio", name="English").click()
    expect(page.get_by_role("heading", name="Step in. Your unwritten work awaits.")).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name="Step in. Your unwritten work awaits.")).to_be_visible()
    # The English face reads the German archive's English display title; the
    # archive itself keeps its own-language identity for the POST to import.
    expect(page.get_by_text("»In the Silent Forest«")).to_be_visible()
    expect(page.get_by_text("»Im Stillen Wald«")).to_have_count(0)
    assert _rows("SELECT id FROM users") == []

    # The wizard header carries the same contract — the step stands alone
    # too, and the mirrored choice is the step's own language.
    page.get_by_role("link", name="Set up the atelier").click()
    expect(page).to_have_url(re.compile(r"/setup/basis$"))
    expect(page.get_by_role("radio", name="English")).to_have_attribute("aria-checked", "true")
    expect(page.get_by_role("navigation", name="Navigation")).to_have_count(0)
    expect(
        page.get_by_role("heading", name="How would you like to begin your literary work?")
    ).to_be_visible()

    # The wizard's switcher is the same contract: back to German, the step
    # speaks it at once, the mirror holds — still no row.
    page.get_by_role("radio", name="Deutsch").click()
    expect(page.get_by_role("heading", name=BASIS_HERO)).to_be_visible()
    assert _rows("SELECT id FROM users") == []

    # The demo path binds with the wizard's answers; the provisioning seam
    # carries the mirror into the fresh row.
    page.goto(BASE + "/setup/basis?demo=im-stillen-wald")
    page.get_by_role("button", name=CONTINUE_TO_STRUCTURE, exact=True).click()
    expect(page).to_have_url(re.compile(r"/setup/structure"))
    page.get_by_role("radio", name="Der Architekt (Plotter)").check()
    page.get_by_role("radio", name="Klassischer 3-Akt-Bogen").check()
    page.get_by_role("button", name=CONTINUE_TO_AI_RULES, exact=True).click()
    expect(page).to_have_url(re.compile(r"/setup/ai-rules"))
    page.get_by_role("radio", name="Stiller Archivar & Faktenchecker").check()
    page.get_by_role("button", name=CONTINUE_TO_PROVISIONING, exact=True).click()
    expect(page).to_have_url(re.compile(r"/setup/provisioning"))
    expect(page.get_by_text("Bereit (100 %)")).to_be_visible()

    # The bound shelf wears the chrome; the row holds the mirrored language.
    page.get_by_role("link", name=BACK_TO_SHELF).click()
    expect(page).to_have_url(BASE + "/")
    expect(page.get_by_role("heading", name=SHELF_TITLE)).to_be_visible()
    expect(page.get_by_role("navigation", name="Navigation")).to_be_visible()
    expect(page.locator("header").get_by_role("button", name="Suchen")).to_be_disabled()
    assert _rows("SELECT locale FROM users") == [("de",)]
    assert_accessible(page)
