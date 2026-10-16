"""Worldbuilding prep for the KB E2E specs (spec §4 helpers package).

Owns the recurring "put the World & Characters surface into a known
state" concerns: navigation into the KB view, mode switches (graph /
wiki / consistency), and API-side seeding of entries + relationships
(the UI's own dispatch surface — the FE api client hits these exact
routes). No auth or wizard concerns (RULE-04 — compose with the
conftest stable_* fixtures and novel_factory).

Selectors verified 2026-10-16 against the live components (Task 7
calibration): sidebar link ``sidebar.worldbuilding`` = "World &
Characters"; ``KBCategorySidebar`` tabs render ``graph.title`` ("Graph")
and ``kb.wiki.tabLabel`` ("Wiki", with a numeric pending badge when > 0)
plus ``SidebarActions``' ``consistency.checkButton`` ("Check
Consistency"); ``KnowledgeGraphControls`` renders the
``graph.searchPlaceholder`` input ("Search entities...") and the stats
bar "N node(s) · M edge(s)".
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests
    from playwright.sync_api import Page

_UI_WAIT_MS: int = 15_000
_KB_LAYOUT = '[data-testid="kb-responsive-layout"]'


def open_worldbuilding(page: Page) -> None:
    """Navigate from the editor into the World & Characters (KB) view."""
    page.get_by_role("link", name=re.compile("World & Characters")).first.click()
    page.locator(_KB_LAYOUT).wait_for(state="visible", timeout=_UI_WAIT_MS)


def open_kb_mode(page: Page, mode: Literal["graph", "wiki", "consistency"]) -> None:
    """Switch the KB view's third column via the category-sidebar tabs."""
    labels = {
        # "Wiki" can carry a pending-count badge in its accessible name
        # ("Wiki 3") — anchor at the start, don't require end-of-string.
        "graph": re.compile(r"^Graph$"),
        "wiki": re.compile(r"^Wiki\b"),
        "consistency": re.compile(r"^Check Consistency$"),
    }
    page.locator(_KB_LAYOUT).get_by_role("button", name=labels[mode]).click()
    _wait_for_mode(page, mode)


def _wait_for_mode(page: Page, mode: str) -> None:
    probes = {
        # Graph controls search input (graph.searchPlaceholder).
        "graph": 'input[placeholder="Search entities..."]',
        # WikiOverviewPanel header title (kb.wiki.overviewTitle).
        "wiki": re.compile(r"Wiki Overview"),
        # ConsistencyCheckPanel header <h3> — the sidebar's "Check
        # Consistency" BUTTON never leaves, so a bare text probe would be
        # satisfied before the mode switch rendered anything (calibrated:
        # probe the panel's own heading element).
        "consistency": re.compile(r"Check Consistency"),
    }
    probe = probes[mode]
    if isinstance(probe, str):
        page.locator(probe).first.wait_for(state="visible", timeout=_UI_WAIT_MS)
    elif mode == "consistency":
        page.locator(_KB_LAYOUT).locator("h3").filter(has_text=probe).first.wait_for(
            state="visible", timeout=_UI_WAIT_MS
        )
    else:
        page.get_by_text(probe).first.wait_for(state="visible", timeout=_UI_WAIT_MS)


def seed_kb_entity(
    authed_request: Callable[..., requests.Response],
    novel_id: str,
    *,
    name: str,
    entity_type: str = "character",
    body: str = "",
) -> dict:
    """Create a KB entry through the entries API (KBEntryCreate shape)."""
    resp = authed_request(
        "POST",
        f"/api/v1/novels/{novel_id}/kb/entries",
        json={
            "entity_type": entity_type,
            "name": name,
            "body": body,
            "metadata": {},
            "tags": [],
        },
    )
    assert resp.status_code == 201, f"{resp.status_code} {resp.text[:300]}"
    return resp.json()


def seed_relationship(
    authed_request: Callable[..., requests.Response],
    novel_id: str,
    source_id: str,
    target_id: str,
    rel_type: str,
) -> dict:
    """Create a relationship through the relationships API."""
    resp = authed_request(
        "POST",
        f"/api/v1/novels/{novel_id}/kb/relationships",
        json={"source_id": source_id, "target_id": target_id, "rel_type": rel_type},
    )
    assert resp.status_code == 201, f"{resp.status_code} {resp.text[:300]}"
    return resp.json()


def track_posts(page: Page, needle: str) -> list[str]:
    """Collect the URLs of POST requests whose URL contains *needle*.

    The probes' ``NetworkCapture`` records failures/provider leaks only —
    request COUNTING needs its own listener (M01 storm pin).
    """
    seen: list[str] = []

    def _on_request(request) -> None:
        if request.method == "POST" and needle in request.url:
            seen.append(request.url)

    page.on("request", _on_request)
    return seen


def capture_json_response(page: Page, needle: str):
    """Attach a listener for the next JSON response matching *needle*.

    Returns a zero-arg getter that blocks (bounded, sync-poll form) until
    the matching response landed and returns its parsed JSON. Attach
    BEFORE the action that triggers the request.
    """
    import time

    slot: list[dict] = []

    def _on_response(response) -> None:
        if needle in response.url and not slot:
            # Tolerant by design: non-JSON responses are simply ignored —
            # the getter asserts on the 60s deadline instead (RULE-11: the
            # failure surfaces at the await, not as a listener exception).
            with contextlib.suppress(Exception):
                slot.append(response.json())

    page.on("response", _on_response)

    def _get() -> dict:
        deadline = time.monotonic() + 60
        while not slot and time.monotonic() < deadline:
            page.wait_for_timeout(250)
        assert slot, f"No JSON response matching {needle!r} within 60s"
        return slot[0]

    return _get
