"""The E2E web server never asks the browser to revalidate the app (#634).

Vite's dev server answers transformed modules with ``Cache-Control: no-cache``,
so a hard navigation revalidates the whole unbundled graph with 304s. Chromium
loses cached module bodies after enough of those and reports
``net::ERR_INSUFFICIENT_RESOURCES`` — the writer's-day sweep, 24 hard
navigations in one context, was exactly that shape. The stack now sets
``NARRE_E2E_NO_HTTP_CACHE``; a second load must fetch the graph fresh, not
revalidate it.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(120)]


def test_a_second_load_revalidates_nothing(page: Page, stack: Stack) -> None:
    page.goto(WEB_URL)
    expect(page.locator("header").get_by_role("button", name="Neues Buch")).to_be_visible()

    responses: list[tuple[int, str]] = []
    page.on("response", lambda response: responses.append((response.status, response.url)))

    page.goto(WEB_URL)
    expect(page.locator("header").get_by_role("button", name="Neues Buch")).to_be_visible()

    revalidated = [url for status, url in responses if status == 304]
    assert revalidated == [], (
        f"{len(revalidated)} responses were revalidated on the second load; the "
        f"E2E web server must send Cache-Control: no-store: {sorted(revalidated)[:5]}"
    )
