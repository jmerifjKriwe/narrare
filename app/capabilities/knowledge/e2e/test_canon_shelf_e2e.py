"""D8's canon rule, watched from the shelf.

The backend bump is only half the rule: an entity edit advances the
novel's updated_at, but the shelf reads that column through the
["novels"] cache's 30 s staleTime — unless the canon-writing mutations
invalidate the key themselves, nothing in the app can observe the rule
for half a minute. This test pins the observation, the way the writing
suite pins it for chapter writes: the books come from the API, not the
new-book dialog (whose own mutation would mask the gap), the hero names
the last-touched book before the edit, and a client-side navigation
back to the shelf — the cache-preserving kind — must find the hero
naming the book that was just written in.
"""

from time import sleep
from typing import TYPE_CHECKING

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:3100"

# The module's database is shared and its order shuffled, so this test
# owns titles no other test uses.
CANON_TITLE = "Die Marschen des Kanons"
OTHER_TITLE = "Der stille Deich"

# Capitalized words steer the fake provider's extraction (it derives
# names from them): Mira, Haus, See, Draußen and Leuchtturm become the
# five suggestions, the way the dock suite's seeding chapter does.
CHAPTER_BODY = "Mira betrat das alte Haus am See. Draußen schwieg der Leuchtturm."


def _row_named(entities: Locator, name: str) -> Locator:
    """The entity list's cell for one exact name — the list's own
    witness, the detail heading's twin notwithstanding."""
    return entities.get_by_role("gridcell", name=name, exact=True)


def _seed_entities(novel_title: str) -> None:
    """A novel with the chapter's five candidates filed as entities,
    through the API the stack runs.

    The correction flows start where review leaves the story: entities
    born through the real review path, no chapter to write first. The
    accepts ride the same lane the product's own seeding does.
    """
    with httpx.Client(base_url=API, timeout=30) as api:
        novel = api.post("/api/writing/novels", json={"title": novel_title})
        novel.raise_for_status()
        novel_id = novel.json()["id"]
        chapter = api.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": "Ankunft"})
        chapter.raise_for_status()
        chapter_id = chapter.json()["id"]
        saved = api.put(f"/api/writing/chapters/{chapter_id}", json={"body": CHAPTER_BODY})
        saved.raise_for_status()
        enqueued = api.post(
            f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id}
        )
        enqueued.raise_for_status()
        # The worker rides the API process: poll the row it settles.
        for _ in range(120):
            job = api.get(f"/api/jobs/{enqueued.json()['job_id']}")
            job.raise_for_status()
            if job.json()["status"] in ("done", "failed"):
                break
            sleep(0.25)
        else:
            pytest.fail("the seeded extraction never settled")
        assert job.json()["status"] == "done"
        suggestions = api.get(f"/api/knowledge/novels/{novel_id}/suggestions")
        suggestions.raise_for_status()
        assert len(suggestions.json()) == 5
        for suggestion in suggestions.json():
            accepted = api.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
            accepted.raise_for_status()


def test_editing_an_entity_makes_its_book_the_hero(page: Page, stack: Stack) -> None:
    """A canon write is a write to the book, and the shelf must say so
    now — not when the cache's half minute runs out.

    The books come from the API, not the new-book dialog: the dialog's
    mutation invalidates the ["novels"] cache itself, which would mask
    the gap this test pins — the dock's canon writes must invalidate it
    too, or the hero names a stale last-touched book for the 30 s
    staleTime.
    """
    _seed_entities(CANON_TITLE)
    other = httpx.post(f"{API}/api/writing/novels", json={"title": OTHER_TITLE})
    other.raise_for_status()

    # The shelf loads, the cache settles: the hero names the other book,
    # the newer one. This is the cached truth a returning writer carries.
    page.goto(f"{WEB}/")
    hero = page.get_by_role("region", name="Mach weiter")
    expect(hero).to_contain_text(OTHER_TITLE)

    # Correct the canon through the real dock: an entity edited, the
    # save settled.
    page.get_by_role("link", name=CANON_TITLE).click()
    expect(page.get_by_role("heading", name=CANON_TITLE)).to_be_visible()
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    entities = dock.get_by_role("region", name="Entitäten")
    _row_named(entities, "Mira").click()
    dock.get_by_role("region", name="Mira").get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Inhalt (Markdown)").fill("Mira trägt immer den roten Schal.")
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).not_to_be_visible()
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Änderungen an Mira wurden gespeichert"
    )

    # Back through the app's own link: a client-side navigation, so the
    # query cache is exactly the one the edit above must have
    # invalidated — a page load would destroy it and hide the gap.
    page.get_by_role("link", name="Alle Romane").click()

    # Well inside the 30 s staleTime, the hero names the book written in.
    expect(hero).to_contain_text(CANON_TITLE)
    expect(hero.get_by_text(OTHER_TITLE)).to_have_count(0)

    assert_accessible(page)
