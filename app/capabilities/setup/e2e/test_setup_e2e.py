"""A fresh database must open on setup and end on the novel it created."""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def test_a_fresh_database_opens_on_setup(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")

    # The root sends an uninstalled instance to setup instead of showing an empty list.
    expect(page).to_have_url(re.compile(r"/setup$"))
    expect(page.get_by_role("heading", name="Willkommen bei Narrare")).to_be_visible()

    page.get_by_label("Titel des Romans").fill("Der Nebel")
    page.get_by_role("button", name="Los geht's").click()

    expect(page.get_by_role("heading", name="Der Nebel")).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name="Der Nebel")).to_be_visible()

    # Setup is closed: the root now lists the novel instead of redirecting.
    page.goto("http://127.0.0.1:3100/")
    expect(page.get_by_role("link", name="Der Nebel")).to_be_visible()
