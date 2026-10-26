"""The §4.6 done criterion in one flow: entity depth proven end to end.

One chapter names eight candidates and nothing else capitalized, so the
fake's derivation proposes the whole vocabulary — one entity per type,
Katharina the character through Schicksal the generic — and each proposal
names its neighbor. The review accepts against the chain's direction:
Schicksal first, whose target is still pending, so its skip is announced
once and visibly (D8: resolution sees existing entities only, so accept
order matters) — then the other seven, each filing the edge its proposal
named. What review filed, the corrections reshape on the same surface:
the body written as Markdown source with aliases and tags as chips, an
edge added by hand with the vocabulary as autocomplete, a merge that
moves Katharina's edge onto the survivor and leaves the folded edge a
flagged self-relation (D3), a delete that takes its edges with it (D4),
the type and tag filters, and the server search that finds Katharina
through the misspelling Kathrina (D6). Real UI, real API, real Postgres;
the fake holds only the LLM/embeddings boundary.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Locator, Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

WEB = "http://127.0.0.1:3100"

NOVEL_TITLE = "Die tiefe Bucht"

# Eight distinct capitalized words — and no other capitalized word — steer
# the fake's derivation to the whole vocabulary: one proposal per type, in
# the contract's order (Katharina the character, Bibliothek the location,
# Gilde the faction, Amulett the object, Uhrwerk the system, Chronik the
# timeline, Sturmflut the event, Schicksal the generic). Entity i proposes
# related_to to entity i+1, the last wrapping to the first.
CHAPTER_BODY = (
    "Katharina betrat die Bibliothek, in der die Gilde das Amulett verbarg. "
    "Uhrwerk und Chronik schwiegen, weil die Sturmflut das Schicksal gewendet hatte."
)

# Name · type as the proposal card prints it, in the queue's order (the
# fake's answer order): one card per type is the cycle's proof.
CARDS_IN_QUEUE_ORDER = (
    "Katharina · Figur",
    "Bibliothek · Ort",
    "Gilde · Fraktion",
    "Amulett · Objekt",
    "Uhrwerk · System",
    "Chronik · Zeitleiste",
    "Sturmflut · Ereignis",
    "Schicksal · Allgemein",
)


def _row_named(entities: Locator, name: str) -> Locator:
    """The entity list's cell for one exact name.

    The detail heading shares the name with the row it opened, so the
    list's own witness is the grid cell.
    """
    return entities.get_by_role("gridcell", name=name, exact=True)


def _accept(dock: Locator, name_and_type: str) -> None:
    """Accept one proposal card, picked by its name · type line.

    The cards are picked by the line, never by a name alone: a proposal
    card may name another card's entity in its relations.
    """
    dock.get_by_role("region", name="Vorgeschlagene Entität").filter(
        has_text=name_and_type
    ).get_by_role("button", name="Übernehmen", exact=True).click()


def test_the_entity_depth_flow_from_review_to_corrections(page: Page, stack: Stack) -> None:
    """Eight types born through review, then every correction the card owes."""
    page.goto(f"{WEB}/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(NOVEL_TITLE)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=NOVEL_TITLE).click()
    expect(page.get_by_role("heading", name=NOVEL_TITLE)).to_be_visible()

    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()
    editor.click()
    page.keyboard.type(CHAPTER_BODY)
    # Extraction reads the saved chapter, so the flow waits for the save
    # the editor itself reports before asking for the job.
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()

    # One extraction over the chapter: the job settles done, its row
    # naming the count the parse produced.
    extract = dock.get_by_role("button", name="Dieses Kapitel durchsuchen")
    extract.click()
    status = dock.locator("[data-job-status]")
    expect(status).to_have_attribute("data-job-status", "done")
    expect(status).to_contain_text("8 Vorschläge gefunden")

    # The queue holds one card per type — the whole vocabulary, in order.
    cards = dock.get_by_role("region", name="Vorgeschlagene Entität")
    expect(cards).to_have_count(len(CARDS_IN_QUEUE_ORDER))
    for name_and_type in CARDS_IN_QUEUE_ORDER:
        expect(cards.filter(has_text=name_and_type)).to_be_visible()
    # The proposals ride the cards: Katharina names her neighbor with the
    # vocabulary's wording, and Schicksal's wrap names Katharina — the
    # proposal the first accept below cannot place yet.
    katharina_card = cards.filter(has_text="Katharina · Figur")
    expect(katharina_card).to_contain_text("Vorgeschlagene Beziehungen")
    expect(katharina_card).to_contain_text("Bibliothek · Verbunden mit")
    schicksal_card = cards.filter(has_text="Schicksal · Allgemein")
    expect(schicksal_card).to_contain_text("Katharina · Verbunden mit")

    # The accepts walk the chain backwards: Schicksal's target does not
    # exist yet (resolution sees existing entities only), so the skip is
    # announced once, naming its target — and every later accept finds its
    # target filed one step before, so its edge is placed for real.
    entities = dock.get_by_role("region", name="Entitäten")
    _accept(dock, "Schicksal · Allgemein")
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Eine Beziehung konnte nicht gesetzt werden: Katharina"
    )
    expect(_row_named(entities, "Schicksal")).to_be_visible()
    for name_and_type in reversed(CARDS_IN_QUEUE_ORDER[:-1]):
        _accept(dock, name_and_type)
        expect(_row_named(entities, name_and_type.split(" · ")[0])).to_be_visible()
    expect(cards).to_have_count(0)
    expect(entities.get_by_role("row")).to_have_count(len(CARDS_IN_QUEUE_ORDER))

    # Edit: the body is Markdown source, aliases and tags are chips. The
    # card shows what was filed, and the save is announced.
    _row_named(entities, "Katharina").click()
    detail = dock.get_by_role("region", name="Katharina")
    # The chain edge the accepts placed: Katharina's proposal resolved.
    expect(detail).to_contain_text("Bibliothek · Verbunden mit")
    detail.get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    aliases = dialog.get_by_label("Aliase")
    aliases.fill("Kathi")
    aliases.press("Enter")
    tags = dialog.get_by_label("Tags", exact=True)
    tags.fill("Hauptfigur")
    tags.press(",")
    dialog.get_by_label("Inhalt (Markdown)").fill(
        "## Herkunft\n\nKatharina wuchs an der Bucht auf."
    )
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).not_to_be_visible()
    expect(detail.get_by_text("Kathi", exact=True)).to_be_visible()
    expect(detail.get_by_text("Hauptfigur", exact=True)).to_be_visible()
    expect(detail.get_by_text("## Herkunft")).to_be_visible()
    expect(detail).to_contain_text("Katharina wuchs an der Bucht auf.")
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Änderungen an Katharina wurden gespeichert"
    )

    # Link two entities by hand: the add row picks Amulett from the
    # novel's entries and the type from the suggested vocabulary.
    detail.get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    target = dialog.get_by_label("Verbinden mit")
    target.fill("Amulett")
    target.press("ArrowDown")
    target.press("Enter")
    expect(target).to_have_value("Amulett")
    kind = dialog.get_by_label("Beziehungsart")
    kind.fill("Besitzt")
    kind.press("ArrowDown")
    kind.press("Enter")
    expect(kind).to_have_value("Besitzt")
    dialog.get_by_label("Notiz (optional)").fill("Seit dem Fest")
    dialog.get_by_role("button", name="Beziehung hinzufügen").click()
    edge_row = dialog.get_by_role("listitem").filter(has_text="Amulett")
    expect(edge_row).to_contain_text("Besitzt")
    expect(edge_row).to_contain_text("Seit dem Fest")
    expect(page.locator("[data-live-announcer]")).to_contain_text("Die Beziehung wurde hinzugefügt")
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).not_to_be_visible()
    expect(detail).to_contain_text("Amulett · Besitzt")

    # The edge has two ends: Amulett's card reads it from the other side.
    _row_named(entities, "Amulett").click()
    amulett = dock.get_by_role("region", name="Amulett")
    expect(amulett).to_contain_text("Katharina · Besitzt")

    # The tag filter later narrows to two rows, so Amulett carries the
    # same tag — filed through the same dialog.
    amulett.get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    tags = dialog.get_by_label("Tags", exact=True)
    tags.fill("Hauptfigur")
    tags.press(",")
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).not_to_be_visible()
    expect(amulett.get_by_text("Hauptfigur", exact=True)).to_be_visible()

    # Merge Bibliothek into Gilde: the survivor keeps the list row, the
    # source's name rides along as an alias, and the edges move — the one
    # that pointed at the source now points at the survivor itself, as a
    # flagged self-relation (D3).
    _row_named(entities, "Bibliothek").click()
    bibliothek = dock.get_by_role("region", name="Bibliothek")
    expect(bibliothek).to_contain_text("Katharina · Verbunden mit")
    bibliothek.get_by_role("button", name="Zusammenführen").click()
    dialog = page.get_by_role("dialog")
    picker = dialog.get_by_label("Zusammenführen mit")
    picker.fill("Gilde")
    picker.press("ArrowDown")
    picker.press("Enter")
    expect(picker).to_have_value("Gilde")
    dialog.get_by_role("button", name="Jetzt zusammenführen").click()
    expect(dialog).not_to_be_visible()
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Bibliothek wurde mit Gilde zusammengeführt"
    )
    expect(_row_named(entities, "Bibliothek")).to_have_count(0)
    expect(entities.get_by_role("row")).to_have_count(len(CARDS_IN_QUEUE_ORDER) - 1)
    gilde = dock.get_by_role("region", name="Gilde")
    expect(gilde.get_by_text("Bibliothek", exact=True)).to_be_visible()
    expect(gilde).to_contain_text("Selbstbezug")
    expect(gilde).to_contain_text("Katharina · Verbunden mit")
    expect(gilde).to_contain_text("Amulett · Verbunden mit")

    # Katharina's edge moved with the merge: it names the survivor now.
    _row_named(entities, "Katharina").click()
    detail = dock.get_by_role("region", name="Katharina")
    expect(detail).to_contain_text("Gilde · Verbunden mit")
    expect(detail).not_to_contain_text("Bibliothek")

    # Delete Chronik: the row goes, and its two edges go with it — the
    # neighbors' cards keep their remaining edges and lose only this one.
    _row_named(entities, "Chronik").click()
    chronik = dock.get_by_role("region", name="Chronik")
    chronik.get_by_role("button", name="Löschen").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Willst du Chronik wirklich löschen?")).to_be_visible()
    dialog.get_by_role("button", name="Endgültig löschen").click()
    expect(dialog).not_to_be_visible()
    expect(page.locator("[data-live-announcer]")).to_contain_text("Chronik wurde gelöscht")
    expect(_row_named(entities, "Chronik")).to_have_count(0)
    expect(entities.get_by_role("row")).to_have_count(len(CARDS_IN_QUEUE_ORDER) - 2)
    _row_named(entities, "Uhrwerk").click()
    uhrwerk = dock.get_by_role("region", name="Uhrwerk")
    expect(uhrwerk).to_contain_text("Amulett · Verbunden mit")
    expect(uhrwerk).not_to_contain_text("Chronik")
    _row_named(entities, "Sturmflut").click()
    sturmflut = dock.get_by_role("region", name="Sturmflut")
    expect(sturmflut).to_contain_text("Schicksal · Verbunden mit")
    expect(sturmflut).not_to_contain_text("Chronik")

    # The filters narrow from the novel's own rows: the type filter to the
    # one character, the tag filter to the two tagged rows, both composed.
    dock.get_by_label("Nach Typ filtern").select_option(label="Figur")
    expect(_row_named(entities, "Katharina")).to_be_visible()
    expect(_row_named(entities, "Gilde")).to_have_count(0)
    expect(entities.get_by_role("row")).to_have_count(1)
    # The narrowed answer's identity, asserted after the settling count:
    # while the narrowed ask refetches, the list keeps its previous page,
    # so the presence above can pass against the unfiltered rows.
    expect(_row_named(entities, "Katharina")).to_have_count(1)
    dock.get_by_label("Nach Typ filtern").select_option(label="Alle Typen")
    dock.get_by_label("Nach Tag filtern").select_option(label="Hauptfigur")
    expect(_row_named(entities, "Katharina")).to_be_visible()
    expect(_row_named(entities, "Amulett")).to_be_visible()
    expect(entities.get_by_role("row")).to_have_count(2)
    expect(_row_named(entities, "Katharina")).to_have_count(1)
    expect(_row_named(entities, "Amulett")).to_have_count(1)
    dock.get_by_label("Nach Typ filtern").select_option(label="Figur")
    expect(_row_named(entities, "Amulett")).to_have_count(0)
    expect(entities.get_by_role("row")).to_have_count(1)
    # The composed answer's identity, after the settling count: the same
    # refetch window as above, so the presence assertions alone would pass
    # against whatever the server still had on screen.
    expect(_row_named(entities, "Katharina")).to_have_count(1)
    dock.get_by_label("Nach Typ filtern").select_option(label="Alle Typen")
    dock.get_by_label("Nach Tag filtern").select_option(label="Alle Tags")
    expect(entities.get_by_role("row")).to_have_count(len(CARDS_IN_QUEUE_ORDER) - 2)

    # The server's trigram tier: the misspelling still finds the row a
    # substring filter could never answer with. Escape closes the box's
    # popup, which holds the rest of the dock aria-hidden.
    search = dock.get_by_label("Entitäten durchsuchen")
    search.fill("Kathrina")
    search.press("Escape")
    expect(_row_named(entities, "Katharina")).to_be_visible()
    expect(_row_named(entities, "Gilde")).to_have_count(0)
    expect(entities.get_by_role("row")).to_have_count(1)
    # The found row's identity, after the settling count: the debounced
    # ask keeps the unfiltered list on screen while it refetches, so the
    # presence above alone would pass whatever the server answered.
    expect(_row_named(entities, "Katharina")).to_have_count(1)
    search.fill("")
    search.press("Escape")
    expect(entities.get_by_role("row")).to_have_count(len(CARDS_IN_QUEUE_ORDER) - 2)

    assert_accessible(page)
