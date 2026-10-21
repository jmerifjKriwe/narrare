"""An uploaded passage must come back from search.

The browser, the API and Postgres with pgvector are the real ones; only the
embedding provider is behind its boundary, served by a local stand-in whose
width the test flips — exactly what a user changing models does.
"""

from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from app.kernel.testing.vendor import EmbeddingsVendor

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

TEXT = "Der Leuchtturm am Horizont war seit Jahren dunkel.\n\nNiemand im Dorf sprach noch über ihn."


def test_uploaded_passage_is_returned_by_search(page: Page, stack: None, tmp_path: Path) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    page.get_by_label("Dokument").set_input_files(str(source))
    page.get_by_label("Titel (optional)").fill("Notizen")
    page.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_text("Notizen")).to_be_visible()

    page.get_by_label("Suchbegriff").fill("Leuchtturm")
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")).to_be_visible()


def test_a_model_change_is_refused_and_reembedding_restores_search(
    page: Page, vendor: EmbeddingsVendor, stack: None, tmp_path: Path
) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    page.get_by_label("Dokument").set_input_files(str(source))
    page.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_text("notizen.txt")).to_be_visible()

    # The user switches models: the vendor answers another width from now on.
    vendor.set_width(768)

    page.get_by_label("Suchbegriff").fill("Leuchtturm")
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Das Embedding-Modell hat sich geändert")).to_be_visible()

    page.get_by_role("button", name="Dokumente neu einbetten").click()
    expect(page.get_by_text("Das Embedding-Modell hat sich geändert")).not_to_be_visible()

    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")).to_be_visible()
