# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The knowledge flow on the real stack (W5 Task 7): the wave's gate.

Seed a novel → upload a document on the sources page → extraction runs →
suggestions appear in the dock → accept → the entity stands in the graph and
as a dock chip → the chip opens its dossier → the consistency check files a
finding → acknowledge. The fake provider is the one permitted boundary fake
(rule 2): its extraction derives the proposals from the seeded prose's
capitalized names, its check derives a contradiction from a name carrying two
numbers — so the prose alone steers every answer the legs assert on. The
document upload rides the real multipart door and the real chunking; the
extraction reads the MANUSCRIPT (the chapter's scenes), never the archive —
the two are the capability's separate real paths, and the flow drives both.

The transient busy faces („Extraktion läuft…", „Prüfung läuft…") are pinned
race-free by the vitest suite's controllable job answers; on the real lane the
job can settle before a browser assertion lands, so these legs pin the
settled truth the busy face promises — the refetched queue — never the
transient ink itself (a timing assertion here would be a flake by
construction). The database reads at the end are the server's own truth:
entities, edges, consumed suggestions, the acknowledged finding, the audit.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.knowledge.e2e.conftest import (
    DATABASE,
    create_chapter,
    create_novel,
    seed_canon,
    set_theme,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.db_rows import rows
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

# One chapter, one scene: the extraction's target is unambiguous, and the
# check's contradiction lives in the same passage. The fake's capitalized-word
# rule names exactly Mira and Kavic (ist/trifft/wartet are lowercase); its
# (name, number) rule reads „Mira ist 34" against „Mira ist 35".
FLOW_PROSE = "Mira ist 34. Mira trifft Kavic. Mira ist 35. Kavic wartet."
FINDING_SUMMARY = "Mira: 34 vs. 35"
FINDING_DETAIL = '"Mira ist 34" vs. "Mira ist 35"'

# The job lane's settle: the worker's idle sleep is 0.5 s, the dock's poll
# 1 s, and the settle refetches the queue before the busy face lifts. The
# ceiling bounds the whole chain under load — it waits on the async contract,
# it does not paper over a race.
SETTLE_TIMEOUT = 20_000


def _seed_flow_novel() -> tuple[str, str]:
    """The book, its one chapter and the prose both jobs read."""
    novel = create_novel("Das Signal")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    chapter_id = str(chapter["id"])
    write_scene(chapter_id, FLOW_PROSE)
    return novel_id, chapter_id


def _open_dock(page: Page, novel_id: str) -> None:
    """The workspace's Wissen tab — the dock registry's own door."""
    page.goto(f"{BASE}/novels/{novel_id}")
    page.get_by_role("group", name="Dock-Ansichten").get_by_role("button", name="Wissen").click()
    expect(page.get_by_test_id("knowledge-dock")).to_be_visible()


def test_the_knowledge_flow_runs_end_to_end(page: Page, installed: Stack) -> None:
    """Upload → extraction → accept → graph + chip → check → acknowledge,
    on the real UI, the real API and the real Postgres — and the database
    carries exactly what the faces claimed."""
    novel_id, _chapter_id = _seed_flow_novel()

    # --- The sources leg: the archive takes the document -------------------
    page.goto(f"{BASE}/novels/{novel_id}/knowledge/sources")
    expect(page.get_by_test_id("sources-page")).to_be_visible()
    expect(page.get_by_test_id("sources-empty")).to_be_visible()
    page.get_by_test_id("sources-file-input").set_input_files(
        {"name": "Notizen.md", "mimeType": "text/markdown", "buffer": b"Mira und Kavic im Hafen."}
    )
    document = page.get_by_test_id("sources-document")
    expect(document).to_be_visible(timeout=SETTLE_TIMEOUT)
    expect(document).to_contain_text("Notizen.md")
    expect(document).to_contain_text("1 Chunk")
    assert rows(DATABASE, "SELECT title FROM documents") == [("Notizen.md",)]
    assert rows(DATABASE, "SELECT count(*) FROM chunks") == [(1,)]

    # --- The dock's honest empty faces --------------------------------------
    _open_dock(page, novel_id)
    expect(page.get_by_test_id("knowledge-entities-empty")).to_be_visible()
    expect(page.get_by_test_id("knowledge-suggestions-empty")).to_be_visible()
    expect(page.get_by_test_id("knowledge-empty")).to_be_visible()
    # The extraction's target note names the chapter the job will read.
    expect(page.get_by_text("Durchsucht: Ankunft")).to_be_visible()

    # --- Extraction: the fake's proposals arrive for review -----------------
    page.get_by_role("button", name="Kapitel extrahieren").click()
    cards = page.get_by_test_id("knowledge-suggestion")
    expect(cards).to_have_count(2, timeout=SETTLE_TIMEOUT)
    # The card's anchor is its h4 — a proposal's relation lines name the
    # OTHER entity, so a text filter alone matches both cards.
    mira_card = cards.filter(has=page.get_by_role("heading", name="Mira", exact=True))
    expect(mira_card).to_contain_text("Vorschlag")
    expect(mira_card).to_contain_text("Figur")
    expect(mira_card).to_contain_text("Mira appears in the chapter.")
    expect(mira_card).to_contain_text("→ Kavic · Verbunden mit")

    # --- Accept: the entity is born, the skipped relation announced once ----
    mira_card.get_by_role("button", name="Übernehmen").click()
    chips = page.get_by_test_id("knowledge-entity-chip")
    expect(chips.filter(has_text="Mira")).to_be_visible(timeout=SETTLE_TIMEOUT)
    expect(page.get_by_text("Eine Beziehung konnte nicht gesetzt werden: Kavic")).to_be_visible()
    # The consumed proposal leaves the queue; its sibling stays live.
    expect(cards).to_have_count(1)
    expect(cards.get_by_role("heading", name="Kavic")).to_be_visible()

    kavic_card = cards.filter(has=page.get_by_role("heading", name="Kavic", exact=True))
    kavic_card.get_by_role("button", name="Übernehmen").click()
    expect(chips.filter(has_text="Kavic")).to_be_visible(timeout=SETTLE_TIMEOUT)
    # The clean accept clears the standing note — it belonged to the one
    # decision that earned it (D8: announced once, persisted nowhere).
    expect(page.get_by_text("Eine Beziehung konnte nicht gesetzt werden: Kavic")).to_have_count(0)
    expect(page.get_by_test_id("knowledge-suggestions-empty")).to_be_visible()
    expect(page.get_by_text("2 Entitäten")).to_be_visible()

    # --- The chip is a door: the graph opens on the entity's dossier --------
    chips.filter(has_text="Mira").click()
    expect(page).to_have_url(re.compile(r"/knowledge/graph\?entity="))
    expect(page.get_by_test_id("graph-page")).to_be_visible()
    dossier = page.get_by_test_id("entity-dossier")
    expect(dossier).to_be_visible()
    expect(dossier.get_by_role("heading", name="Mira")).to_be_visible()
    expect(dossier).to_contain_text("Mira appears in the chapter.")
    # The accepted canon: two nodes, the one edge whose target stood at
    # accept time (Kavic → Mira; Mira's own proposal skipped while Kavic
    # was still pending).
    expect(page.get_by_test_id("graph-node")).to_have_count(2)
    expect(page.get_by_test_id("graph-edge")).to_have_count(1)
    expect(page.get_by_test_id("graph-edge")).to_have_attribute(
        "aria-label", "Kavic → Mira, Verbunden mit"
    )

    # --- The check: a finding reads the manuscript's truth ------------------
    _open_dock(page, novel_id)
    page.get_by_role("button", name="Konsistenz prüfen").click()
    finding = page.get_by_test_id("knowledge-finding")
    expect(finding).to_have_count(1, timeout=SETTLE_TIMEOUT)
    expect(finding).to_contain_text(FINDING_SUMMARY)
    expect(finding).to_contain_text(FINDING_DETAIL)
    expect(finding).to_contain_text("Konflikt")
    expect(page.get_by_text("1 offener Befund")).to_be_visible()
    # The workspace header's badge reads the same queue (the #866 family).
    expect(page.get_by_test_id("dock-findings-badge")).to_have_attribute(
        "aria-label", "1 offener Befund"
    )

    # --- Acknowledge: consumed, the text stays as it is ---------------------
    finding.get_by_role("button", name="Zur Kenntnis nehmen").click()
    expect(page.get_by_test_id("knowledge-empty")).to_be_visible(timeout=SETTLE_TIMEOUT)
    expect(page.get_by_text("0 offene Befunde")).to_be_visible()
    expect(page.get_by_test_id("dock-findings-badge")).to_have_attribute(
        "aria-label", "0 offene Befunde"
    )
    assert_accessible(page)

    # --- The server's truth --------------------------------------------------
    assert rows(DATABASE, "SELECT name, type FROM entities ORDER BY created_at") == [
        ("Mira", "character"),
        ("Kavic", "location"),
    ]
    assert rows(
        DATABASE,
        "SELECT f.name, t.name, r.relation_type FROM entity_relations r"
        " JOIN entities f ON f.id = r.from_entity_id"
        " JOIN entities t ON t.id = r.to_entity_id",
    ) == [("Kavic", "Mira", "related_to")]
    assert rows(DATABASE, "SELECT name, status FROM entity_suggestions ORDER BY created_at") == [
        ("Mira", "accepted"),
        ("Kavic", "accepted"),
    ]
    assert rows(DATABASE, "SELECT summary, status FROM consistency_findings") == [
        (FINDING_SUMMARY, "acknowledged")
    ]
    # Both jobs audited: the fake tier, free, named for the novel's tasks.
    assert rows(
        DATABASE,
        "SELECT task_key, provider_kind, status, cost_usd FROM llm_calls ORDER BY created_at",
    ) == [
        ("knowledge.extract-entities", "fake", "ok", 0.0),
        ("knowledge.check-consistency", "fake", "ok", 0.0),
    ]


def test_a_discarded_suggestion_creates_nothing(page: Page, installed: Stack) -> None:
    """Discard consumes the proposal without creating an entity — the queue
    shrinks, the canon stays empty, and the row records the decision."""
    novel_id, _chapter_id = _seed_flow_novel()
    page.goto(f"{BASE}/novels/{novel_id}/knowledge")
    expect(page.get_by_test_id("knowledge-dock")).to_be_visible()
    page.get_by_role("button", name="Kapitel extrahieren").click()
    cards = page.get_by_test_id("knowledge-suggestion")
    expect(cards).to_have_count(2, timeout=SETTLE_TIMEOUT)

    # The card's anchor is its h4 — a proposal's relation lines name the
    # other entity, so a text filter alone matches both cards.
    mira = cards.filter(has=page.get_by_role("heading", name="Mira", exact=True))
    mira.get_by_role("button", name="Verwerfen").click()
    expect(cards).to_have_count(1, timeout=SETTLE_TIMEOUT)
    expect(page.get_by_test_id("knowledge-entities-empty")).to_be_visible()
    assert rows(DATABASE, "SELECT count(*) FROM entities") == [(0,)]
    assert rows(DATABASE, "SELECT name, status FROM entity_suggestions ORDER BY created_at") == [
        ("Mira", "discarded"),
        ("Kavic", "pending"),
    ]


def test_a_book_without_chapters_offers_no_extraction(page: Page, installed: Stack) -> None:
    """No chapter, no trigger: the honest note stands instead of a button
    that would enqueue nothing."""
    novel = create_novel("Ein unbeschriebenes Werk")
    page.goto(f"{BASE}/novels/{novel['id']}/knowledge")
    expect(page.get_by_test_id("knowledge-dock")).to_be_visible()
    expect(page.get_by_text("Noch keine Kapitel, die extrahiert werden könnten.")).to_be_visible()
    expect(page.get_by_role("button", name="Kapitel extrahieren")).to_have_count(0)


def test_the_dark_dock_face_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The settings row's dark theme, adopted at boot: the dock's chips and
    queues render on the tokens' dark halves and clear the axe floor."""
    set_theme("dark")
    novel_id, chapter_id = _seed_flow_novel()
    seed_canon(novel_id, chapter_id)
    page.goto(f"{BASE}/novels/{novel_id}/knowledge")
    expect(page.get_by_test_id("knowledge-dock")).to_be_visible()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_test_id("knowledge-entity-chip")).to_have_count(2)
    assert_accessible(page)
