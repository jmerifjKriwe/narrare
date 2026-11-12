# ruff: noqa: RUF001

"""Showcase seed: the four novels the Stitch screens name, populated for a
visual comparison against ``docs/design/stitch/screens/``.

This is not a gate. It seeds the shelf and one workspace the way the design
drafts draw them — same titles, chapter counts and word totals — so a
screenshot taken here can be held next to ``shelf.webp`` / ``workspace*.webp``
and read for drift. The per-test minimal seeds stay the source of truth for
the automated suites; this spec exists for the human eye.

Run with ``just test-e2e writing`` and read the screenshots from
``/tmp/opencode/showcase/``.
"""

import re
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.stack import API_URL, WEB_URL

pytestmark = [pytest.mark.e2e, pytest.mark.showcase, pytest.mark.timeout(300)]

API = API_URL
BASE = WEB_URL
SHOTS = Path("/tmp/opencode/showcase")  # noqa: S108

# The prose the Stitch workspace screen actually draws for Dead Signal's
# first chapter, padded to the screen's stated 765 words so the shelf's
# 3.384-word total still holds.
DEAD_SIGNAL_CH1_EXCERPT = (
    "Ich war gerade dabei, die Quantensensoren neu zu kalibrieren – schon wieder –, "
    "als ARIAs Stimme durch das tiefe, metallische Brummen des Maschinendecks schnitt. "
    "Irgendwo hinter der Konsole klickte ein Relais, einmal, und das Summen des Decks "
    "verstummte für einen Wimpernschlag. Ein Herzschlag im Vakuum. "
    "»Calder?« ARIAs Synthesizer schwankte in einer Frequenz, die sie eigentlich nicht "
    "nutzen sollte. Es klang fast wie ein Zögern, fast menschlich, fast furchtsam. "
    "»Der Subraum-Kanal auf Relais 7 empfängt eine periodische Welle. Sie stammt nicht "
    "aus dem imperialen Netz.« "
    "Ich legte das Justierwerkzeug auf die geriffelte Werkbank und trat vor das "
    "Hauptdisplay. Auf der mattschwarzen Phosphorfläche zog sich ein dünner, "
    "bernsteinfarbener Impuls durch die Rauschlinien – ein regelmäßiger Rhythmus aus "
    "vier langen und zwei abgehackten Tönen. Kein Standard-Transpondercode der "
    "Explorationsgilde, kein automatisches Notsignal verlassener Bergbaudrohnen. "
    "Ich beugte mich vor, meine Finger strichen über die kühle Messingleiste des "
    "Terminals. »Quelle triangulieren«, befahl ich leise, während die Luftfilter leise "
    "zischten. "
    "»Das Signal befindet sich nicht im freien Raum, Calder«, antwortete ARIA nach drei "
    "quälenden Sekunden. »Es kommt aus dem Inneren unserer Hülle. Sektion D-4.«"
)


def _body_for(target_words: int, prefix: str = "") -> str:
    """A body of exactly ``target_words`` words, optionally carrying ``prefix`` first."""
    prefix_words = prefix.split()
    if len(prefix_words) >= target_words:
        return " ".join(prefix_words[:target_words])
    filler = ["Wort"] * (target_words - len(prefix_words))
    return " ".join(prefix_words + filler)


def _seed_novel(
    client: httpx.Client,
    title: str,
    genre: str,
    chapters: list[tuple[int, str]],
) -> str:
    """Create a novel with chapters whose bodies hit the given word counts.

    ``chapters`` is a list of (target_words, prefix_text) pairs; an empty
    list yields a novel with no chapters.
    """
    novel = client.post(f"{API}/api/writing/novels", json={"title": title, "genre": genre})
    novel.raise_for_status()
    novel_id = str(novel.json()["id"])
    for index, (words, prefix) in enumerate(chapters, start=1):
        chapter = client.post(
            f"{API}/api/writing/novels/{novel_id}/chapters",
            json={"title": f"Kapitel {index}"},
        )
        chapter.raise_for_status()
        chapter_id = chapter.json()["id"]
        if words:
            written = client.put(
                f"{API}/api/writing/chapters/{chapter_id}",
                json={"body": _body_for(words, prefix)},
            )
            written.raise_for_status()
    return novel_id


def _seed_all(client: httpx.Client) -> dict[str, str]:
    # Titles, genres and (chapter count, word totals) taken from the Stitch
    # screens: shelf.webp (4 cards) and workspace*.webp (Dead Signal hero).
    # Seed order matters for the shelf hero: the last-touched novel wins it,
    # and Stitch draws Dead Signal as the hero, so it is seeded last.
    ids: dict[str, str] = {}
    ids["winterhaus"] = _seed_novel(client, "Winterhaus", "Mystery", [])
    ids["salt_road"] = _seed_novel(
        client, "The Salt Road", "Lit Fiction", [(2012, "") for _ in range(12)]
    )
    ids["arkona"] = _seed_novel(
        client, "Der Nebel von Arkona", "Historisch", [(2240, "") for _ in range(5)]
    )
    ids["dead_signal"] = _seed_novel(
        client,
        "Dead Signal",
        "Sci-Fi",
        [(765, DEAD_SIGNAL_CH1_EXCERPT), (1062, ""), (1557, "")],
    )
    return ids


def _shelf_shot(page: Page, path: Path) -> None:
    """The whole shelf at the draft's width, not the first viewport.

    The shell is exactly one viewport tall and `main` owns the page scroll, so
    `full_page` would capture the fold alone. The viewport grows to the
    scroller's overflow for the frame — measured after widening to the
    archive's 1600 px, since the text reflows — and returns to the fixture's
    size.
    """
    page.set_viewport_size({"width": 1600, "height": 1000})
    # The activity banner is the last block the shelf's queries fill; the
    # dark capture measured before it landed and cut the banner off.
    page.get_by_role("heading", name=re.compile("Heutiges Schreibziel")).wait_for()
    height = int(
        page.evaluate(
            """() => {
                const main = document.querySelector("main");
                if (!main) return document.documentElement.scrollHeight;
                return Math.ceil(
                    main.scrollHeight + (window.innerHeight - main.clientHeight),
                );
            }"""
        )
    )
    page.set_viewport_size({"width": 1600, "height": height})
    try:
        page.screenshot(path=str(path))
    finally:
        page.set_viewport_size({"width": 1280, "height": 720})


def test_showcase_captures_stitch_comparison(page: Page, stack) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120) as client:
        ids = _seed_all(client)

    # Shelf: hold next to docs/design/stitch/screens/library/shelf.webp
    page.goto(f"{BASE}/")
    expect(page.get_by_role("heading", name="Das Bücherregal")).to_be_visible()
    for title in ("Dead Signal", "Winterhaus", "The Salt Road", "Der Nebel von Arkona"):
        expect(page.get_by_role("link", name=title).first).to_be_visible()
    _shelf_shot(page, SHOTS / "shelf.png")

    # The same seeded shelf in the reader's chosen dark, hold next to
    # docs/design/stitch/screens/library/shelf-dark.webp. The theme is the
    # stored choice, not `color_scheme`: the dark artifact must prove the
    # setting the reader makes.
    page.request.patch(f"{API}/api/settings/theme", data={"theme": "dark"})
    page.goto(f"{BASE}/")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_role("heading", name="Das Bücherregal")).to_be_visible()
    _shelf_shot(page, SHOTS / "shelf-dark.png")
    page.request.patch(f"{API}/api/settings/theme", data={"theme": None})
    page.goto(f"{BASE}/")
    expect(page.locator("html")).not_to_have_attribute("data-theme", "dark")

    # Workspace: hold next to docs/design/stitch/screens/writing/workspace*.webp
    page.goto(f"{BASE}/novels/{ids['dead_signal']}")
    expect(page.get_by_role("heading", name="Dead Signal")).to_be_visible()
    page.screenshot(path=str(SHOTS / "workspace-dead-signal.png"), full_page=True)
