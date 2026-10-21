"""A question asked in the browser must come back quoting the uploaded passage.

The upload happens through the knowledge page, so the passage the answer cites is
one that reached Postgres in this same run. The browser, the API and Postgres are
the real ones; the provider and the embedding model are the catalog's fakes.
"""

from pathlib import Path  # noqa: TC003

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

PASSAGE = "Der Leuchtturm am Horizont war seit Jahren dunkel."


def test_answer_quotes_the_uploaded_passage(page: Page, stack: None, tmp_path: Path) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(PASSAGE, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    page.get_by_label("Dokument").set_input_files(str(source))
    page.get_by_label("Titel (optional)").fill("Notizen")
    page.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_text("Notizen")).to_be_visible()

    page.goto("http://127.0.0.1:3100/chat")
    page.get_by_label("Frage").fill("Wo war der Leuchtturm?")
    page.get_by_role("button", name="Fragen").click()

    expect(page.get_by_role("region", name="Antwort")).to_contain_text(PASSAGE)
    expect(page.get_by_role("region", name="Quellen")).to_contain_text("Notizen")
