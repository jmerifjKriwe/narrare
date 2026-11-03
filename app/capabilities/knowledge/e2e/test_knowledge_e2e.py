"""An uploaded passage must come back from search.

The browser, the API and Postgres with pgvector are the real ones; only the
embedding provider is behind its boundary, served by a local stand-in whose
width the test flips — exactly what a user changing models does.
"""

from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack
    from app.kernel.testing.vendor import EmbeddingsVendor

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

TEXT = "Der Leuchtturm am Horizont war seit Jahren dunkel.\n\nNiemand im Dorf sprach noch über ihn."


def _upload(page: Page, source: Path, title: str | None) -> None:
    """Upload one document through the one "+ Dokument" dialog.

    The page holds exactly one control that opens the upload form; the
    dialog owns the fields and stays open on a refusal.
    """
    page.get_by_role("button", name="+ Dokument").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Dokument").set_input_files(str(source))
    if title is not None:
        dialog.get_by_label("Titel (optional)").fill(title)
    dialog.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_the_documents_area_is_one_panel_with_one_upload_control(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    """The documents area is a Panel list with exactly one "+ Dokument" control.

    The upload form lives behind the dialog, not on the page: the page
    must not carry a second way to upload, and the list must carry its
    heading so the area is nameable.
    """
    page.goto("http://127.0.0.1:3100/knowledge")
    expect(page.get_by_role("heading", name="Dokumente")).to_be_visible()
    expect(page.get_by_role("button", name="+ Dokument")).to_have_count(1)

    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")
    _upload(page, source, "Notizen")
    expect(page.get_by_text("Notizen")).to_be_visible()

    assert_accessible(page)


def test_uploaded_passage_is_returned_by_search(page: Page, stack: Stack, tmp_path: Path) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    _upload(page, source, "Notizen")
    expect(page.get_by_text("Notizen")).to_be_visible()

    page.get_by_label("Suchbegriff").fill("Leuchtturm")
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")).to_be_visible()

    assert_accessible(page)


def test_a_model_change_is_refused_and_reembedding_restores_search(
    page: Page, vendor: EmbeddingsVendor, stack: Stack, tmp_path: Path
) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    _upload(page, source, None)
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

    assert_accessible(page)


def test_a_refused_reembed_names_itself_and_the_retry_heals(
    page: Page, vendor: EmbeddingsVendor, stack: Stack, tmp_path: Path
) -> None:
    """A re-embed that does not happen must say so (F15).

    The old page returned silently on a refused re-embed: the model-change
    warning stood forever and nothing said the repair had failed. The
    refusal is an alert beside the warning, and the notice's retry is the
    way back once the local service answers again.
    """
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    _upload(page, source, None)
    expect(page.get_by_text("notizen.txt")).to_be_visible()

    vendor.set_width(768)
    page.get_by_label("Suchbegriff").fill("Leuchtturm")
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Das Embedding-Modell hat sich geändert")).to_be_visible()

    # The local service dies mid-flow: the re-embed cannot happen.
    stack.stop_api()
    try:
        page.get_by_role("button", name="Dokumente neu einbetten").click()
        expect(page.get_by_role("alert").filter(has_text="fehlgeschlagen")).to_be_visible()
    finally:
        stack.start_api()

    # The retry on the notice is the way back: the repair runs, the
    # warning retires, and search speaks again.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_text("Das Embedding-Modell hat sich geändert")).not_to_be_visible()
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")).to_be_visible()

    assert_accessible(page)


def test_a_dead_service_on_load_names_the_outage(page: Page, stack: Stack) -> None:
    """An unreachable API on /knowledge reads as an outage, never as empty (F14).

    The old page read the failed load as "Noch keine Dokumente" — the empty
    state worn as a mask over a missing answer. The outage is an alert with
    a working retry; the empty claim must stay silent.
    """
    page.goto("http://127.0.0.1:3100/knowledge")
    expect(page.get_by_text("Noch keine Dokumente")).to_be_visible()

    stack.stop_api()
    try:
        page.reload()
        expect(
            page.get_by_role("alert").filter(has_text="Dokumente konnten nicht geladen")
        ).to_be_visible()
        # The empty state must not stand in for the missing answer.
        expect(page.get_by_text("Noch keine Dokumente")).to_have_count(0)
    finally:
        stack.start_api()

    # Recovery through the notice's retry: the honest answer again, no
    # alert left standing.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_text("Noch keine Dokumente")).to_be_visible()
    expect(page.get_by_role("alert")).to_have_count(0)

    assert_accessible(page)
